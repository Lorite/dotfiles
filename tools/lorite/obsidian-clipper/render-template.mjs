#!/usr/bin/env node
/**
 * Render a Web Clipper template with Knap, from data we already have, with no page to clip.
 *
 * The clipper CLI renders a template by fetching a URL and extracting it. Several of our
 * own generators already hold the data (a `gh` API response, a Zotero item) and only need
 * the rendering half. Before Knap that meant hand-maintaining a Python copy of the
 * template's note shape, which then drifted from the template it was copied from. This
 * gives those generators the real template instead.
 *
 * Protocol: one JSON object on stdin, one on stdout.
 *
 *   in : { "template": <a clipper template object>,
 *          "variables": { "title": "...", "url": "...", ... },
 *          "propertyTypes": { "<name>": "text|multitext|datetime|..." } }
 *   out: { "noteName": "...", "frontmatter": "---\n...---\n", "content": "...",
 *          "properties": [{ "name": ..., "type": ..., "value": ... }], "errors": [...] }
 *
 * Variable names are passed to Knap verbatim, so a `{{selector:...}}` expression in the
 * template resolves from a variables key of that exact name. That is how a generator feeds
 * page-scraped fields (an issue author, a timestamp) from structured data instead of a DOM.
 *
 * `generateFrontmatter` below is transcribed from the clipper's own `src/utils/shared.ts`
 * so property types serialise identically. Re-check it against that file after a pin bump:
 * the clipper's API bundle would be the better source, but `dist/api.mjs` currently fails
 * to load (defuddle is CommonJS and the bundle imports it as ESM).
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const CLIPPER_DIR = process.env.OBSIDIAN_CLIPPER_DIR
    || path.join(process.env.HOME, '.local/share/obsidian-clipper-cli');

async function loadFromClipper(name) {
    const require = createRequire(path.join(CLIPPER_DIR, 'node_modules', name, 'package.json'));
    return import(pathToFileURL(require.resolve(name)).href);
}

const escapeDoubleQuotes = (s) => String(s).replace(/"/g, '\\"');

/** Transcribed from the clipper's src/utils/shared.ts — keep in sync after a pin bump. */
function generateFrontmatter(properties, propertyTypes = {}) {
    let frontmatter = '---\n';
    for (const property of properties) {
        const trimmedName = property.name.trim();
        const needsQuotes = /[:\s{}[\],&*#?|<>=!%@\\-]/.test(trimmedName)
            || /^\d/.test(trimmedName)
            || /^(true|false|null|yes|no|on|off)$/i.test(trimmedName);
        const propertyKey = needsQuotes
            ? (property.name.includes('"')
                ? `'${property.name.replace(/'/g, "''")}'`
                : `"${property.name}"`)
            : property.name;
        frontmatter += `${propertyKey}:`;

        const propertyType = propertyTypes[property.name] || property.type || 'text';
        const value = property.value ?? '';

        switch (propertyType) {
            case 'multitext': {
                let items;
                if (value.trim().startsWith('["') && value.trim().endsWith('"]')) {
                    try {
                        items = JSON.parse(value);
                    } catch {
                        items = value.split(',').map((i) => i.trim());
                    }
                } else {
                    items = value.split(/,(?![^[]*\]\])/).map((i) => i.trim());
                }
                items = items.filter((i) => i !== '');
                frontmatter += '\n';
                for (const item of items) frontmatter += `  - "${escapeDoubleQuotes(item)}"\n`;
                break;
            }
            case 'number': {
                const numeric = value.replace(/[^\d.-]/g, '');
                frontmatter += numeric ? ` ${parseFloat(numeric)}\n` : '\n';
                break;
            }
            case 'checkbox': {
                const checked = typeof value === 'boolean' ? value : value === 'true';
                frontmatter += ` ${checked}\n`;
                break;
            }
            case 'date':
            case 'datetime':
                frontmatter += value.trim() !== '' ? ` ${value}\n` : '\n';
                break;
            default:
                frontmatter += value.trim() !== '' ? ` "${escapeDoubleQuotes(value)}"\n` : '\n';
        }
    }
    return frontmatter + '---\n';
}

/** Transcribed from the clipper's formatPropertyValue. */
function formatPropertyValue(dayjs, value, type, templateValue) {
    switch (type) {
        case 'number': {
            const numeric = value.replace(/[^\d.-]/g, '');
            return numeric ? parseFloat(numeric).toString() : value;
        }
        case 'checkbox':
            return (value.toLowerCase() === 'true' || value === '1').toString();
        case 'date':
        case 'datetime': {
            // A template that already formats with |date: has said what it wants.
            if (!templateValue.includes('|date:')) {
                const d = dayjs(value);
                if (d.isValid()) return d.format(type === 'date' ? 'YYYY-MM-DD' : 'YYYY-MM-DDTHH:mm:ssZ');
            }
            return value;
        }
        default:
            return value;
    }
}

async function main() {
    const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
    const { template, variables = {}, propertyTypes = {} } = payload;
    if (!template) {
        console.error('payload needs a "template" object');
        process.exit(2);
    }

    const knap = await loadFromClipper('knap');
    const dayjsMod = await loadFromClipper('dayjs');
    const dayjs = dayjsMod.default || dayjsMod;

    const passthrough = (v) => v;
    const engine = knap.createEngine({
        filters: {
            ...knap.standardFilters,
            // Clipper's own three. `markdown` converts extracted HTML, which a caller that
            // already holds Markdown does not need, so it passes the value straight through.
            markdown: passthrough,
            html_to_json: passthrough,
            remove_html: passthrough,
        },
    });

    const errors = [];
    const render = async (text) => {
        if (!text) return '';
        const result = await engine.render(text, {
            variables,
            // An unknown variable renders empty, which is what the clipper does for a
            // selector that matched nothing. Silence here is the same silence as a miss.
            resolveVariable: (name) => (name in variables ? variables[name] : ''),
        });
        for (const e of result.errors) errors.push(e.message);
        return result.output;
    };

    const noteName = (await render(template.noteNameFormat || '')).trim();
    const properties = [];
    for (const p of template.properties || []) {
        const type = propertyTypes[p.name] || p.type || 'text';
        const raw = await render(p.value || '');
        properties.push({ name: p.name, type, value: formatPropertyValue(dayjs, raw, type, p.value || '') });
    }
    const content = await render(template.noteContentFormat || '');

    process.stdout.write(JSON.stringify({
        noteName,
        properties,
        frontmatter: generateFrontmatter(properties, propertyTypes),
        content,
        path: template.path || '',
        errors,
    }, null, 2));
}

main();
