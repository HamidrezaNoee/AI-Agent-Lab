// Execute the production logout handler with mocked HTTP/location, without a browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/production/app.js'), 'utf8');
const handler = source.slice(source.indexOf('async function signOut(){'), source.indexOf('function recordActivity(){'));
async function check(ok) {
  const calls = [], destinations = [], errors = [];
  const app = {csrf: 'csrf-test', user: {bootstrap_mode: true}};
  const context = {
    app, window: {location: {assign: url => destinations.push(url)}},
    fetch: async (url, options) => {calls.push({url, options}); return {ok};},
    sessionExpired: () => {app.user = null; app.csrf = null;},
    toast: message => errors.push(message),
  };
  vm.createContext(context);
  vm.runInContext(handler, context);
  await context.signOut();
  assert.equal(calls[0].url, '/admin/api/logout');
  assert.equal(calls[0].options.headers['X-AVAN-ADMIN-CSRF'], 'csrf-test');
  assert.deepEqual(destinations, ok ? ['/auth/login'] : []);
  assert.equal(errors.length, ok ? 0 : 1);
  assert.equal(app.user === null, ok);
}
(async () => {
  await check(true);
  await check(false);
  console.log('Logout routing passed: public login after successful local logout, failed logout retained.');
})().catch(error => {console.error(error); process.exitCode = 1;});
