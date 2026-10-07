const test = require('node:test');
const assert = require('node:assert/strict');
const { buildQuery, buildUrl } = require('../tv-query.js');

const stations = ['CNN', 'KGO'];

test('requires a directory-listed station and a positive keyword', () => {
  assert.equal(buildQuery('climate', 'cnn', stations), 'climate station:CNN');
  assert.equal(buildQuery('climate station:CNN', '', stations), 'climate station:CNN');
  assert.throws(() => buildQuery('climate', '', stations), /频道 ID/);
  assert.throws(() => buildQuery('station:CNN', '', stations), /正向关键词/);
  assert.throws(() => buildQuery('climate', 'CNNW', stations), /官方频道目录/);
});

test('rejects Archive IDs and conflicting or malformed station filters', () => {
  assert.throws(
    () => buildQuery('CNNW_20261007_040000_The_Story_Is_With_Elex_Michaelson', 'CNN', stations),
    /Archive 条目 ID/
  );
  assert.throws(() => buildQuery('climate station:', 'CNN', stations), /格式不完整/);
  assert.throws(() => buildQuery('climate station:KGO', 'CNN', stations), /不一致/);
  assert.throws(() => buildQuery('-climate station:CNN', '', stations), /正向关键词/);
});

test('URL-encodes query syntax without changing its meaning', () => {
  const url = buildUrl('https://api.gdeltproject.org/api/v2/tv/tv', 'clipgallery', 'climate station:CNN');
  const parsed = new URL(url);
  assert.equal(parsed.searchParams.get('query'), 'climate station:CNN');
  assert.equal(parsed.searchParams.get('mode'), 'clipgallery');
});
