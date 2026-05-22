module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  settings: {
    react: { version: 'detect' },
  },
  plugins: ['@typescript-eslint', 'react', 'react-hooks', 'jsx-a11y', 'import'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
  ],
  rules: {
    'react/prop-types': 'off',
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/consistent-type-imports': 'warn',
    '@typescript-eslint/no-unused-vars': [
      'error',
      { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
    ],
    'react/react-in-jsx-scope': 'off',
    'no-console': ['warn', { allow: ['warn', 'error'] }],
  },
  ignorePatterns: ['dist', 'node_modules', 'vite.config.ts', '.eslintrc.cjs'],
};
