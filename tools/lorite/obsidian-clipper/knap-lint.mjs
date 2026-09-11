#!/usr/bin/env node
/**
 * Lint (and optionally repair) Web Clipper templates against Knap, the template engine
 * upstream obsidian-clipper moved to in `a9d33ce` ("Move templating to Knap", 2026-09-03).
 *
 * Why this exists: the extension stores many template expressions with escaped quotes
 * (`{{words|calc:\"/238\"}}`), and the old bundled renderer turned `\"` into a DOUBLED
 * quoted literal. We used to repair that inside the CLI
 * (patches/0003-Unescape-quotes-in-filter-arguments.patch), but that file is gone upstream
 * and Knap sees the same malformed input. Repairing the TEMPLATES instead fixes the browser
 * extension too, and removes a patch we would otherwise carry forever.
 *
 * Loud breakage is only part of it. Measured across this vault's 33 templates, 16
 * expressions are rejected outright (`calc`, `replace`), but many more are accepted and
 * SILENTLY WRONG: `date:\"YYYY-MM-DDTHH:mm\"` emits the timestamp wrapped in literal
 * quotes, `join:\"\n- \"` leaks quotes between list items, a CSS selector written
 * `[data-testid=\"x\"]` is queried with the backslashes still in it, and an interpreter
 * prompt written `{{\"...\"}}` is no longer recognised as a prompt at all, so its
 * instructions render into the note as body text. That is why this repairs every escaped
 * expression, not only the ones that error.
 *
 * Why this is not the unsafe regex rewrite that `export-templates.py` used to warn about:
 * every repair is PARSER-GATED. A repair is only kept when Knap renders the repaired
 * expression with no errors, so a rewrite can never make a template worse than it was.
 * Measured on the current settings export: all 461 escaped quotes sit inside a `{{...}}`
 * span, and no prompt contains the `}}` that would defeat the span regex. Both conditions
 * are re-checked on every run, and a span that fails them is reported and left alone.
 *
 * Usage:
 *   ./knap-lint.mjs                          # lint ~/.config/obsidian-clipper-cli/templates
 *   ./knap-lint.mjs --fix                    # repair them in place
 *   ./knap-lint.mjs --settings <file> --fix  # repair the Web Clipper settings export itself,
 *                                            # so re-importing it fixes the extension too
 *
 * Exit code is 1 when problems remain, so it can gate a build.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const DEFAULT_DIR = path.join(process.env.HOME, '.config/obsidian-clipper-cli/templates');
const CLIPPER_DIR = process.env.OBSIDIAN_CLIPPER_DIR
    || path.join(process.env.HOME, '.local/share/obsidian-clipper-cli');

/**
 * Knap comes from the clipper build's own node_modules, so the linter always checks against
 * the exact version the CLI will render with rather than whatever `npx` resolves today.
 */
async function loadKnap() {
    const candidates = [
        path.join(CLIPPER_DIR, 'node_modules/knap'),
        path.join(path.dirname(new URL(import.meta.url).pathname), 'node_modules/knap'),
    ];
    for (const base of candidates) {
        try {
            const require = createRequire(path.join(base, 'package.json'));
            const entry = require.resolve('knap');
            const mod = await import(pathToFileURL(entry).href);
            const version = JSON.parse(fs.readFileSync(path.join(base, 'package.json'), 'utf8')).version;
            return { ...mod, __version: version, __from: base };
        } catch {
            /* try the next candidate */
        }
    }
    console.error('Could not find knap. Run ./build-cli.sh first, which installs it into');
    console.error(`  ${CLIPPER_DIR}/node_modules/knap`);
    process.exit(2);
}

/** Clipper adds three filters on top of Knap's standard set; stub them so they are not "unknown". */
function buildEngine(knap) {
    const passthrough = (value) => value;
    return knap.createEngine({
        filters: {
            ...knap.standardFilters,
            markdown: passthrough,
            html_to_json: passthrough,
            remove_html: passthrough,
        },
    });
}

/** An expression is healthy when Knap renders it without errors. Unresolvable variables are fine. */
async function check(engine, expr) {
    const result = await engine.render(expr, { variables: {}, resolveVariable: () => undefined });
    return result.errors;
}

/**
 * Repair 1: undo the extension's escaping.
 *
 * It escapes both quotes and backslashes, so `join:\"\\n- \"` means the separator
 * newline + "- ". A quote-only replace would leave `join:"\\n- "`, a literal backslash-n,
 * which is why this is a single left-to-right pass that consumes each `\X` once instead of
 * two independent replaces (whose order would corrupt the `\\"` sequence either way).
 */
function unescapeQuotes(expr) {
    if (!expr.includes('\\"')) return null;
    let out = '';
    for (let i = 0; i < expr.length; i++) {
        if (expr[i] === '\\' && (expr[i + 1] === '"' || expr[i + 1] === '\\')) {
            out += expr[i + 1];
            i++;
        } else {
            out += expr[i];
        }
    }
    return out;
}

/**
 * A repaired expression must have balanced quotes. `replace:"\"":""` legitimately escapes a
 * quote as the search VALUE, and unescaping it would yield `replace:""":""` — which knap may
 * still parse, so the error gate alone would not catch it. Odd quote counts are rejected.
 */
function quotesBalanced(expr) {
    return ((expr.match(/"/g) || []).length % 2) === 0;
}

/**
 * Repair 2: the old bundled `replace` filter accepted several comma-separated pairs
 * (`replace:"PT","","S",""`); Knap's takes exactly one `old:new` pair. Chain them instead.
 */
function chainReplacePairs(expr) {
    const pattern = /\|\s*replace:((?:\s*"(?:[^"\\]|\\.)*"\s*,)+\s*"(?:[^"\\]|\\.)*"\s*)/g;
    let changed = false;
    const out = expr.replace(pattern, (whole, args) => {
        const values = args.match(/"(?:[^"\\]|\\.)*"/g) || [];
        if (values.length < 2 || values.length % 2 !== 0) return whole;
        changed = true;
        const pairs = [];
        for (let i = 0; i < values.length; i += 2) pairs.push(`${values[i]}:${values[i + 1]}`);
        return pairs.map((p) => `|replace:${p}`).join('');
    });
    return changed ? out : null;
}

/**
 * Peel the escaping to a fixed point, keeping the deepest level Knap still accepts.
 *
 * Some expressions are escaped twice over (LinkedIn's `span[dir=\\"ltr\\"]`), so one pass
 * leaves them escaped and a later run would flag them again. Peeling stops at the first
 * unbalanced result, which is what protects `replace:"\"":""` — there the escaped quote is
 * the value being searched for, and one peel makes it `replace:""":""`, an odd quote count.
 */
async function peelEscaping(engine, expr) {
    let clean = null;   // deepest level Knap renders without errors
    let peeled = null;  // deepest level at all, which may still need a second repair
    let current = expr;
    for (let depth = 0; depth < 4; depth++) {
        const candidate = unescapeQuotes(current);
        if (!candidate || candidate === current || !quotesBalanced(candidate)) break;
        current = candidate;
        peeled = candidate;
        const errors = await check(engine, candidate);
        if (errors.length === 0) clean = candidate;
    }
    return { clean, peeled };
}

/** Never guesses: a repair Knap does not accept is discarded and the expression is left as it was. */
async function repair(engine, expr) {
    const { clean, peeled } = await peelEscaping(engine, expr);

    // Knap's `replace` takes a single old:new pair; the old bundled filter took several
    // comma-separated ones. Chain them, on top of the unescaped text — `replace:\"PT\",\"\"`
    // has to lose its backslashes before the pairs are even findable.
    const chained = chainReplacePairs(peeled || expr);
    if (chained && quotesBalanced(chained) && (await check(engine, chained)).length === 0) {
        return { fixed: chained, via: 'chain-replace-pairs' };
    }
    if (clean) return { fixed: clean, via: 'unescape' };
    return null;
}

/**
 * A span is a candidate when Knap rejects it, or when it carries escaped quotes (which Knap
 * accepts and renders wrongly). Everything else is already correct and is never touched.
 *
 * The span regex cannot delimit an expression whose own text contains `}}`, which is only
 * plausible inside an interpreter prompt. Such a span is reported and skipped rather than
 * repaired, so the corruption the old `export-templates.py` note warns about cannot happen.
 */
function containsUndelimitableText(str, span) {
    if (!/^\{\{\s*\\?"/.test(span)) return false;
    const quotes = (span.match(/\\?"/g) || []).length;
    return quotes % 2 !== 0 || str.includes(span.slice(0, -2) + '}}' + '}}');
}

async function processString(engine, str, { fix }) {
    const spans = str.match(/\{\{[^{}]*\}\}/g);
    if (!spans) return { str, findings: [] };
    const findings = [];
    let out = str;
    for (const span of new Set(spans)) {
        const errors = await check(engine, span);
        const escaped = span.includes('\\"');
        if (errors.length === 0 && !escaped) continue;
        const rejected = errors.length > 0;
        const message = rejected ? errors[0].message : 'escaped quotes may render literally';
        if (containsUndelimitableText(str, span)) {
            findings.push({ span, message: 'prompt text may contain }}', fixed: null, rejected });
            continue;
        }
        let fixed = null;
        if (fix) {
            const result = await repair(engine, span);
            if (result) {
                fixed = result.fixed;
                out = out.replaceAll(span, fixed);
            }
        }
        findings.push({ span, message, fixed, rejected });
    }
    return { str: out, findings };
}

/** Rebuild any JSON value, repairing the strings inside it. */
async function walk(engine, value, opts, findings, where) {
    if (typeof value === 'string') {
        const result = await processString(engine, value, opts);
        for (const f of result.findings) findings.push({ ...f, where });
        return result.str;
    }
    if (Array.isArray(value)) {
        const out = [];
        for (let i = 0; i < value.length; i++) out.push(await walk(engine, value[i], opts, findings, where));
        return out;
    }
    if (value && typeof value === 'object') {
        const out = {};
        for (const [k, v] of Object.entries(value)) out[k] = await walk(engine, v, opts, findings, where);
        return out;
    }
    return value;
}

function parseArgs(argv) {
    const opts = { dir: DEFAULT_DIR, settings: null, fix: false };
    for (let i = 0; i < argv.length; i++) {
        const a = argv[i];
        if (a === '--fix') opts.fix = true;
        else if (a === '--dir') opts.dir = argv[++i];
        else if (a === '--settings') opts.settings = argv[++i];
        else if (a === '-h' || a === '--help') { console.log(fs.readFileSync(new URL(import.meta.url), 'utf8').split('*/')[0]); process.exit(0); }
        else { console.error(`Unknown argument: ${a}`); process.exit(2); }
    }
    return opts;
}

async function main() {
    const opts = parseArgs(process.argv.slice(2));
    const knap = await loadKnap();
    const engine = buildEngine(knap);

    // A settings export is one JSON file; an exported template set is a directory of them.
    const targets = opts.settings
        ? [opts.settings]
        : fs.readdirSync(opts.dir).filter((f) => f.endsWith('.json')).sort().map((f) => path.join(opts.dir, f));

    // property-types.json sits beside the templates directory, not inside it, and its
    // `defaultValue` fields are template expressions too — one of them carries the same
    // broken `replace` the YouTube templates did. Lint it with them.
    if (!opts.settings) {
        const propertyTypes = path.join(path.dirname(opts.dir), 'property-types.json');
        if (fs.existsSync(propertyTypes)) targets.push(propertyTypes);
    }

    if (targets.length === 0) {
        console.error(`No templates found in ${opts.dir}. Run ./export-templates.py first.`);
        process.exit(2);
    }

    console.log(`knap ${knap.__version} (from ${knap.__from})`);
    console.log(`${opts.fix ? 'Repairing' : 'Linting'} ${targets.length} file(s)\n`);

    let broken = 0;
    let skipped = 0;
    let repaired = 0;
    const brief = (s) => (s.length > 100 ? s.slice(0, 100) + ' …' : s);
    for (const file of targets) {
        const original = fs.readFileSync(file, 'utf8');
        const findings = [];
        const data = await walk(engine, JSON.parse(original), opts, findings, path.basename(file));
        if (findings.length === 0) continue;
        for (const f of findings) {
            if (f.fixed) {
                repaired++;
                console.log(`  FIXED  ${f.where}`);
                console.log(`    was: ${brief(f.span)}`);
                console.log(`    now: ${brief(f.fixed)}`);
            } else if (f.rejected) {
                // Knap refuses to render this and no repair made it clean: a real problem.
                broken++;
                console.log(`  ERROR  ${f.where}`);
                console.log(`    expr: ${brief(f.span)}`);
                console.log(`    knap: ${f.message}`);
            } else if (!opts.fix) {
                // Report mode attempts no repairs, so it must not claim a repair failed.
                skipped++;
                console.log(`  NEEDS FIX  ${f.where}`);
                console.log(`    expr: ${brief(f.span)}`);
                console.log(`    why : ${f.message} — run --fix`);
            } else {
                // Knap accepts it as written and no safe repair exists, e.g. `replace:"\"":""`,
                // where the escaped quote IS the value being searched for. Left alone on purpose.
                skipped++;
                console.log(`  SKIP   ${f.where}`);
                console.log(`    expr: ${brief(f.span)}`);
                console.log(`    why : ${f.message}, and no repair kept knap happy`);
            }
        }
        if (opts.fix && findings.some((f) => f.fixed)) {
            // Keep the file's own trailing-newline convention. The Web Clipper settings export
            // ends without one, and adding it would put an unrelated line in the vault's diff.
            const trailer = original.endsWith('\n') ? '\n' : '';
            fs.writeFileSync(file, JSON.stringify(data, null, 2) + trailer);
        }
    }

    console.log();
    if (repaired) console.log(`Repaired ${repaired} expression(s).`);
    if (skipped) {
        console.log(opts.fix
            ? `Left ${skipped} expression(s) alone (knap accepts them; review the SKIP list above).`
            : `${skipped} expression(s) need --fix.`);
    }
    if (broken) {
        console.log(`${broken} expression(s) rejected by knap and not repairable.`);
        process.exit(1);
    }
    console.log(repaired ? 'No expressions are rejected by knap.' : 'All templates already render cleanly.');
}

main();
