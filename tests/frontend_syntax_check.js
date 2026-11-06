// Revisión estática de TODO el frontend sin navegador ni build (mantenimiento fase 4).
//   node tests/frontend_syntax_check.js
// 1. Sintaxis: cada .js/.jsx de src/ se parsea con Babel (JSX).
// 2. Texto JSX sospechoso: restos de código pegados como texto (p. ej. «))}» que pasó en Productos el
//    2026-11-05): llaves, «=>», «))»… dentro de un texto JSX. La sintaxis no lo detecta porque es JSX válido.
// 3. Imports locales rotos: `@/…` y rutas relativas que no apuntan a ningún archivo.
// 4. Nombres importados que el archivo de destino no exporta (solo para imports locales con nombre).
const path = require('path');
const fs = require('fs');

const FE = path.join(__dirname, '..', 'frontend');
const SRC = path.join(FE, 'src');
const parser = require(path.join(FE, 'node_modules', '@babel', 'parser'));

const files = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(js|jsx)$/.test(e.name)) files.push(p);
  }
})(SRC);

const parse = (code) => parser.parse(code, { sourceType: 'module', plugins: ['jsx'] });
const resolve = (from, spec) => {
  const base = spec.startsWith('@/') ? path.join(SRC, spec.slice(2)) : path.resolve(path.dirname(from), spec);
  for (const c of [base, `${base}.js`, `${base}.jsx`, path.join(base, 'index.js'), path.join(base, 'index.jsx')]) {
    if (fs.existsSync(c) && fs.statSync(c).isFile()) return c;
  }
  return null;
};

const asts = {};
const problems = [];
for (const f of files) {
  try { asts[f] = parse(fs.readFileSync(f, 'utf8')); }
  catch (e) { problems.push(`SINTAXIS ${path.relative(FE, f)}: ${e.message}`); }
}

const exportsOf = (f) => {
  const ast = asts[f];
  if (!ast) return null;
  const names = new Set();
  let star = false;
  for (const n of ast.program.body) {
    if (n.type === 'ExportDefaultDeclaration') names.add('default');
    if (n.type === 'ExportAllDeclaration') star = true;
    if (n.type === 'ExportNamedDeclaration') {
      if (n.declaration) {
        if (n.declaration.id) names.add(n.declaration.id.name);
        (n.declaration.declarations || []).forEach((d) => d.id && d.id.name && names.add(d.id.name));
      }
      (n.specifiers || []).forEach((s) => names.add(s.exported.name));
    }
  }
  return star ? null : names;   // con `export *` no se puede saber: no se revisa
};

for (const [f, ast] of Object.entries(asts)) {
  const rel = path.relative(FE, f);
  (function walk(n) {
    if (!n || typeof n.type !== 'string') return;
    if (n.type === 'JSXText' && /[{}]|=>|\)\)\s*[};]|;\s*$/.test(n.value)) problems.push(`TEXTO JSX ${rel}:${n.loc.start.line}: ${JSON.stringify(n.value.trim())}`);
    for (const k of Object.keys(n)) {
      const v = n[k];
      if (Array.isArray(v)) v.forEach(walk);
      else if (v && typeof v === 'object' && k !== 'loc') walk(v);
    }
  })(ast.program);
  for (const n of ast.program.body) {
    if (n.type !== 'ImportDeclaration' && !(n.type === 'ExportNamedDeclaration' && n.source)) continue;
    const spec = n.source.value;
    if (!(spec.startsWith('@/') || spec.startsWith('.'))) continue;
    if (/\.(css|svg|png|jpg)$/.test(spec)) continue;
    const target = resolve(f, spec);
    if (!target) { problems.push(`IMPORT ROTO ${rel}: '${spec}' no existe`); continue; }
    const exp = exportsOf(target);
    if (!exp) continue;
    for (const s of n.specifiers || []) {
      const name = s.type === 'ImportDefaultSpecifier' ? 'default' : s.type === 'ImportSpecifier' ? s.imported.name
        : s.type === 'ExportSpecifier' ? s.local.name : null;
      if (name && !exp.has(name)) problems.push(`NO EXPORTADO ${rel}: '${name}' no está en ${path.relative(FE, target)}`);
    }
  }
}

problems.forEach((p) => console.log(`FAIL ${p}`));
const total = files.length;
console.log(`\n${total - new Set(problems.map((p) => p.split(' ')[1].split(':')[0])).size}/${total} pruebas OK`);
process.exit(problems.length ? 1 : 0);
