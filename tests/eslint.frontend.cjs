// Lint del frontend para el CI y scripts/run_all_tests.sh (mantenimiento fase 4).
// Falla con errores reales (nombres sin definir, JSX con componentes inexistentes);
// los imports/variables sin usar solo se reportan como aviso.
const path = require('path');
const FE = path.join(__dirname, '..', 'frontend', 'node_modules');
const react = require(path.join(FE, 'eslint-plugin-react'));
const globals = require(path.join(FE, 'globals'));
const reactHooks = require(path.join(FE, 'eslint-plugin-react-hooks'));

module.exports = [{
  files: ['**/*.js', '**/*.jsx'],
  languageOptions: {
    ecmaVersion: 2022, sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } },
    globals: { ...globals.browser, process: 'readonly' },
  },
  plugins: { react, 'react-hooks': reactHooks },
  linterOptions: { reportUnusedDisableDirectives: 'off' },
  rules: {
    'no-undef': 'error',
    'react/jsx-no-undef': 'error',
    'react/jsx-uses-vars': 'error',
    'react/jsx-uses-react': 'error',
    'no-unused-vars': ['warn', { vars: 'all', args: 'none', varsIgnorePattern: '^React$', caughtErrors: 'none' }],
  },
}];
