/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');

const repoRoot = path.resolve(__dirname, '..');
const geojsonPath = path.resolve(repoRoot, process.argv[2] || 'Data/va_precincts.geojson');
const outputPath = path.resolve(repoRoot, process.argv[3] || 'Data/precinct_polling_places.json');
const sourceUrl = 'https://www.elections.virginia.gov/resultsreports/registration-statistics/polling-places/';
const sourceFileUrl = 'https://www.elections.virginia.gov/media/registration-statistics/2025-November-General-Election-Day-Polling-Locations-20251022.xlsx';

function decodeHtml(raw) {
  const entities = {
    amp: '&', apos: "'", gt: '>', lt: '<', nbsp: ' ', quot: '"',
    '#39': "'", '#x27': "'", '#8217': '’', '#x2019': '’'
  };
  return String(raw || '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&([^;]+);/g, (full, entity) => {
      if (Object.prototype.hasOwnProperty.call(entities, entity)) return entities[entity];
      if (/^#\d+$/.test(entity)) return String.fromCodePoint(Number(entity.slice(1)));
      if (/^#x[0-9a-f]+$/i.test(entity)) return String.fromCodePoint(parseInt(entity.slice(2), 16));
      return full;
    })
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeLocality(raw) {
  return String(raw || '').trim().replace(/\s+/g, ' ').toUpperCase();
}

function normalizeCode(raw) {
  const code = String(raw || '').trim().toUpperCase().replace(/[^A-Z0-9.-]/g, '');
  return /^\d+$/.test(code) ? String(Number(code)) : code;
}

function splitPrecinct(raw) {
  const match = String(raw || '').match(/^\s*([A-Z0-9.-]+)\s*-\s*(.+?)\s*$/i);
  return match
    ? { code: normalizeCode(match[1]), name: match[2].trim().replace(/\s+/g, ' ').toUpperCase() }
    : { code: '', name: '' };
}

function parseOfficialRows(html) {
  const rowMatches = [...String(html || '').matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)];
  const matrix = rowMatches.map(match =>
    [...match[1].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/gi)].map(cell => decodeHtml(cell[1]))
  ).filter(row => row.length >= 9);
  if (!matrix.length) throw new Error('No polling-place table rows found.');
  const headers = matrix[0];
  if (!headers.includes('Voting Precinct Name') || !headers.includes('Location')) {
    throw new Error(`Unexpected polling-place headers: ${headers.join(', ')}`);
  }
  return matrix.slice(1).map(row =>
    Object.fromEntries(headers.map((header, index) => [header, row[index] || '']))
  );
}

function pollingPlaceRecord(row, sourceCode, matchType) {
  return {
    precinct_name: row['Voting Precinct Name'] || '',
    location: row.Location || '',
    address_line_1: row['Address Line 1'] || '',
    address_line_2: row['Address Line 2'] || '',
    city: row.City || '',
    state: row.State || '',
    zip: String(row['Zip Code'] || ''),
    room: row['Poll Location Voting Room'] || '',
    source_precinct_code: sourceCode,
    match_type: matchType
  };
}

async function main() {
  const response = await fetch(sourceUrl);
  if (!response.ok) throw new Error(`Polling-place download failed: HTTP ${response.status}`);
  const officialRows = parseOfficialRows(await response.text());
  const electionName = officialRows[0]?.['Election Name'] || '2025 November General';
  const pollingByKey = new Map();
  const pollingByCountyName = new Map();

  for (const row of officialRows) {
    const locality = normalizeLocality(row['Locality Name']);
    const parsed = splitPrecinct(row['Voting Precinct Name']);
    if (!locality || !parsed.code) continue;
    pollingByKey.set(`${locality}\u0000${parsed.code}`, row);
    if (parsed.name && !/^PRECINCT\b/i.test(parsed.name)) {
      const nameKey = `${locality}\u0000${parsed.name}`;
      if (!pollingByCountyName.has(nameKey)) pollingByCountyName.set(nameKey, []);
      pollingByCountyName.get(nameKey).push(row);
    }
  }

  const geojson = JSON.parse(fs.readFileSync(geojsonPath, 'utf8').replace(/^\uFEFF/, ''));
  const countyMaps = new Map();
  const unmatched = [];
  const matchCounts = { exact: 0, parent: 0, name: 0, county_renumber: 0 };

  for (const feature of geojson.features || []) {
    const props = feature.properties || {};
    const locality = normalizeLocality(props.county_norm || props.county_nam);
    const code = normalizeCode(props.prec_id);
    let row = pollingByKey.get(`${locality}\u0000${code}`);
    let matchType = 'exact';

    if (!row && /^\d{2,}$/.test(code)) {
      row = pollingByKey.get(`${locality}\u0000${code.slice(0, -1)}`);
      matchType = 'parent';
    }
    if (!row) {
      const geometryName = splitPrecinct(props.precinct_name).name;
      const nameRows = pollingByCountyName.get(`${locality}\u0000${geometryName}`) || [];
      if (geometryName && nameRows.length === 1) {
        [row] = nameRows;
        matchType = 'name';
      }
    }
    if (!row && locality === 'ARLINGTON COUNTY' && /^\d+$/.test(code)) {
      row = pollingByKey.get(`${locality}\u0000${Number(code) + 100}`);
      matchType = 'county_renumber';
    }
    if (!row) {
      unmatched.push({ county: locality, code, precinct_name: props.precinct_name || '' });
      continue;
    }

    const sourceCode = splitPrecinct(row['Voting Precinct Name']).code;
    if (!countyMaps.has(locality)) countyMaps.set(locality, new Map());
    countyMaps.get(locality).set(code, pollingPlaceRecord(row, sourceCode, matchType));
    matchCounts[matchType] += 1;
  }

  const counties = {};
  for (const locality of [...countyMaps.keys()].sort()) {
    counties[locality] = Object.fromEntries(
      [...countyMaps.get(locality).entries()].sort(([a], [b]) => {
        const an = /^\d+$/.test(a);
        const bn = /^\d+$/.test(b);
        if (an && bn) return Number(a) - Number(b);
        if (an !== bn) return an ? -1 : 1;
        return a.localeCompare(b);
      })
    );
  }

  const matched = Object.values(matchCounts).reduce((sum, count) => sum + count, 0);
  const payload = {
    version: 1,
    generated_at: new Date().toISOString(),
    election_name: electionName,
    source_url: sourceUrl,
    source_file_url: sourceFileUrl,
    coverage: {
      geometry_precincts: (geojson.features || []).length,
      matched,
      unmatched: unmatched.length,
      match_counts: matchCounts
    },
    counties,
    unmatched
  };
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  console.log(`Wrote ${path.relative(repoRoot, outputPath)} with ${matched}/${payload.coverage.geometry_precincts} current polling-place matches; ${unmatched.length} unmatched.`);
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
