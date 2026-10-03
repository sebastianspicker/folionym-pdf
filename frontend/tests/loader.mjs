import ts from 'typescript';
import { readFile } from 'node:fs/promises';
export async function resolve(specifier, context, next) {
  try { return await next(specifier, context); } catch (error) {
    if (!specifier.startsWith('.')) throw error;
    for (const suffix of ['.ts', '.tsx', '/index.ts']) {
      try { return await next(specifier + suffix, context); } catch { /* Try next source extension. */ }
    }
    throw error;
  }
}
export async function load(url, context, next) {
  if (!/\.tsx?$/.test(url)) return next(url, context);
  const source = (await readFile(new URL(url), 'utf8')).replaceAll('import.meta.env.MODE', '"test"').replaceAll('import.meta.env.BASE_URL', '"/"');
  return { format: 'module', shortCircuit: true, source: ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText };
}
