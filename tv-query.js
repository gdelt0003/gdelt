(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.GdeltTvQuery = api;
})(typeof globalThis === 'undefined' ? this : globalThis, function () {
  const archiveId = /\b[A-Z0-9]+_\d{8}_\d{6}_[A-Z0-9_]+\b/i;
  const stationFilter = /\bstation\s*:\s*([A-Za-z0-9_-]+)/ig;
  const malformedStation = /\bstation\s*:\s*(?=$|[\s()])/i;
  const tokenPattern = /"[^"]*"|'[^']*'|\S+/g;

  function buildQuery(query, station, stationIds) {
    query = String(query || '').trim();
    if (!query) throw new Error('请输入至少一个正向关键词或短语。');
    if (archiveId.test(query)) throw new Error('Archive 条目 ID 不是 GDELT TV 搜索词，请使用字幕关键词。');
    if (malformedStation.test(query)) throw new Error('查询中的频道筛选格式不完整。');

    const knownStations = new Set(Array.from(stationIds || [], id => String(id).trim().toUpperCase()).filter(Boolean));
    const queryStations = Array.from(query.matchAll(stationFilter), match => match[1].toUpperCase());
    const selectedStation = String(station || '').trim().toUpperCase();

    if (selectedStation && !knownStations.has(selectedStation)) {
      throw new Error('频道 ID 不在 GDELT 官方频道目录中。');
    }
    if (queryStations.some(id => !knownStations.has(id))) {
      throw new Error('查询中含有不在 GDELT 官方频道目录中的频道 ID。');
    }
    if (selectedStation && queryStations.length && !queryStations.includes(selectedStation)) {
      throw new Error('所选频道与查询中的 station 筛选不一致。');
    }
    if (!queryStations.length) {
      if (!selectedStation) throw new Error('请填写 GDELT 官方频道目录中的频道 ID。');
      query += ` station:${selectedStation}`;
    }

    const terms = query.replace(stationFilter, ' ').match(tokenPattern) || [];
    const positiveTerms = terms.filter(token =>
      !['OR', 'AND'].includes(token.toUpperCase())
      && !token.startsWith('-')
      && token.replace(/["'()]/g, '').length > 0
    );
    if (!positiveTerms.length) throw new Error('频道筛选之外还必须提供正向关键词或短语。');
    return query;
  }

  function buildUrl(base, mode, query) {
    const url = new URL(base);
    url.searchParams.set('format', 'html');
    url.searchParams.set('mode', mode);
    url.searchParams.set('query', query);
    url.searchParams.set('timespan', '7d');
    return url.toString();
  }

  return { buildQuery, buildUrl };
});
