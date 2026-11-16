export default {
  root: '/work',
  cacheDir: '/tmp/vite-cache',
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    pool: 'forks',
    maxWorkers: 1,
    fileParallelism: false,
    testTimeout: 10000,
  },
};
