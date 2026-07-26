/* eslint-disable no-console */
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const repoRoot = path.resolve(__dirname, '..');
const geojsonPath = path.resolve(repoRoot, process.argv[2] || 'Data/va_precincts_current.geojson');
const outputPath = path.resolve(repoRoot, process.argv[3] || 'Data/precinct_friendly_names.json');
const dataDir = path.join(repoRoot, 'Data');
const geometryBridgePath = path.join(dataDir, 'precinct_geometry_version_crosswalk.csv');

const uppercaseTokens = new Set([
  'AME', 'CME', 'EMS', 'JFK', 'JMU', 'JR', 'II', 'III', 'IV', 'MLK',
  'NE', 'NW', 'SE', 'SW', 'UMC', 'VFD', 'VFW', 'YMCA'
]);
const manualOverrides = {
  'FAIRFAX COUNTY': {
    '700': 'Fairfax Court'
  },
  'HAMPTON CITY': {
    '113': 'Hampton University'
  },
  'WASHINGTON COUNTY': {
    '204': 'Woodland Hills'
  },
  'WYTHE COUNTY': {
    '603': 'Evergreen'
  }
};

function normalizeLocality(raw) {
  return String(raw || '').trim().replace(/\s+/g, ' ').toUpperCase();
}

function normalizeCode(raw) {
  const code = String(raw || '').trim().toUpperCase().replace(/[^A-Z0-9.-]/g, '');
  return /^\d+$/.test(code) ? String(Number(code)) : code;
}

function splitCodeAndName(raw) {
  const value = String(raw || '').trim().replace(/\s+/g, ' ');
  const match = value.match(/^\s*([A-Z0-9.-]+)\s*-\s*(.+?)\s*$/i);
  return match ? [normalizeCode(match[1]), match[2].trim()] : ['', ''];
}

function isUsableName(raw, code = '') {
  const name = String(raw || '').trim();
  if (!name || /^VTD(?:\s+\d+)?$/i.test(name)) return false;
  const normalizedCode = normalizeCode(code);
  if (/^PRECINCT\s+[A-Z0-9.-]+$/i.test(name)) {
    const genericCode = normalizeCode(name.replace(/^PRECINCT\s+/i, ''));
    if (!normalizedCode || genericCode === normalizedCode) return false;
  }
  return true;
}

function formatDisplayName(raw) {
  let name = String(raw || '').trim().replace(/_/g, ' ').replace(/\s+/g, ' ');
  name = name.replace(/\s+\(STATE DISTRICT UNITED STATES OF AMERICA\)$/i, '');
  name = name.toLowerCase().replace(/\b([a-z])/g, (m, c) => c.toUpperCase());
  name = name.replace(/\bMc([a-z])/g, (m, c) => `Mc${c.toUpperCase()}`);
  name = name.replace(/'S\b/g, "'s");
  name = name.replace(/\bMt\b(?=\s+[A-Z])/g, 'Mt.');
  name = name.replace(/\bSt\b(?=\s+[A-Z])/g, 'St.');
  for (const token of uppercaseTokens) {
    const titled = token.charAt(0) + token.slice(1).toLowerCase();
    name = name.replace(new RegExp(`\\b${titled}\\b`, 'g'), token);
  }
  name = name.replace(/\b([A-Za-z])\.([A-Za-z])\./g, (m, a, b) => `${a.toUpperCase()}.${b.toUpperCase()}.`);
  return name.trim();
}

function parseCsvLine(line) {
  const values = [];
  let value = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (quoted && line[i + 1] === '"') {
        value += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === ',' && !quoted) {
      values.push(value);
      value = '';
    } else {
      value += char;
    }
  }
  values.push(value);
  return values;
}

function collectGeometryBridgeNames() {
  const out = new Map();
  if (!fs.existsSync(geometryBridgePath)) return out;
  const lines = fs.readFileSync(geometryBridgePath, 'utf8')
    .replace(/^\uFEFF/, '')
    .split(/\r?\n/)
    .filter(Boolean);
  if (!lines.length) return out;
  const headers = parseCsvLine(lines.shift());

  for (const line of lines) {
    const values = parseCsvLine(line);
    const row = {};
    headers.forEach((header, index) => { row[header] = values[index] || ''; });
    const locality = normalizeLocality(row.locality);
    const currentCode = normalizeCode(row.current_prec_id);
    const [, legacyName] = splitCodeAndName(row.legacy_precinct_name);
    if (!locality || !currentCode || !isUsableName(legacyName)) continue;
    const key = `${locality}\u0000${currentCode}`;
    const score = Number(row.legacy_area_overlap || 0);
    const previous = out.get(key);
    if (!previous || score > previous.score) {
      out.set(key, { name: legacyName, score });
    }
  }

  return new Map([...out].map(([key, value]) => [key, value.name]));
}

async function collectRecentElectionNames() {
  const files = fs.readdirSync(dataDir)
    .filter(name => /^Election Results_.*\.csv$/i.test(name)
      || /^Virginia_Elections_Database__2024_.*_including_precincts\.csv$/i.test(name))
    .sort();
  const newestByKey = new Map();

  for (const filename of files) {
    const filenameYear = (filename.match(/(20\d{2})/) || [])[1] || '';
    const fallbackDate = filenameYear ? `${filenameYear}-01-01` : '';
    const input = fs.createReadStream(path.join(dataDir, filename), { encoding: 'utf8' });
    const lines = readline.createInterface({ input, crlfDelay: Infinity });
    let headers = null;

    for await (const line of lines) {
      const values = parseCsvLine(line.replace(/^\uFEFF/, ''));
      if (!headers) {
        headers = values;
        continue;
      }
      const row = {};
      headers.forEach((header, index) => { row[header] = values[index] || ''; });
      const locality = normalizeLocality(row.LocalityName || row['County/City']);
      const [code, name] = splitCodeAndName(row.PrecinctName || row.Pct);
      if (!locality || !code || !isUsableName(name, code)) continue;

      const key = `${locality}\u0000${code}`;
      const electionDate = String(row.ElectionDate || fallbackDate).trim();
      const current = newestByKey.get(key);
      if (!current || electionDate > current.date) {
        newestByKey.set(key, { date: electionDate, counts: new Map([[name, 1]]) });
      } else if (electionDate === current.date) {
        current.counts.set(name, (current.counts.get(name) || 0) + 1);
      }
    }
  }

  const out = new Map();
  for (const [key, entry] of newestByKey) {
    const best = [...entry.counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
    if (best) out.set(key, best[0]);
  }
  return out;
}

function sortCodes(entries) {
  return entries.sort(([a], [b]) => {
    const aNumeric = /^\d+$/.test(a);
    const bNumeric = /^\d+$/.test(b);
    if (aNumeric && bNumeric) return Number(a) - Number(b);
    if (aNumeric !== bNumeric) return aNumeric ? -1 : 1;
    return a.localeCompare(b);
  });
}

async function main() {
  const geojson = JSON.parse(fs.readFileSync(geojsonPath, 'utf8').replace(/^\uFEFF/, ''));
  const recentNames = await collectRecentElectionNames();
  const bridgeNames = collectGeometryBridgeNames();
  const countyMaps = new Map();
  const unresolved = [];

  for (const feature of geojson.features || []) {
    const props = feature.properties || {};
    const locality = normalizeLocality(props.county_norm || props.county_nam);
    let code = normalizeCode(props.prec_id);
    const [labelCode, geometryName] = splitCodeAndName(props.precinct_name);
    if (!code && labelCode) code = labelCode;
    if (!locality || !code) continue;

    const key = `${locality}\u0000${code}`;
    let name = recentNames.get(key) || '';
    if (!isUsableName(name, code)) name = '';
    if (!name && isUsableName(geometryName, code)) name = geometryName;
    if (!name) name = bridgeNames.get(key) || '';

    // Census VTD split pieces use a final sub-piece digit (4011, 4012, ...).
    // Give each piece its official parent precinct name when available.
    if (!name && /^\d{2,}$/.test(code)) {
      name = recentNames.get(`${locality}\u0000${code.slice(0, -1)}`) || '';
    }
    name = manualOverrides[locality]?.[code] || name;

    if (!name) {
      unresolved.push({ county: locality, code });
      name = `Precinct ${code}`;
    }
    if (!countyMaps.has(locality)) countyMaps.set(locality, new Map());
    countyMaps.get(locality).set(code, formatDisplayName(name));
  }

  const counties = {};
  for (const locality of [...countyMaps.keys()].sort()) {
    counties[locality] = Object.fromEntries(sortCodes([...countyMaps.get(locality).entries()]));
  }

  const payload = {
    version: 1,
    generated_at: new Date().toISOString(),
    generated_from: [
      path.relative(repoRoot, geojsonPath).replace(/\\/g, '/'),
      'Data/precinct_geometry_version_crosswalk.csv',
      'Data/Election Results_*.csv',
      'Data/Virginia_Elections_Database__2024_*_including_precincts.csv'
    ],
    counties,
    unresolved: unresolved.sort((a, b) => a.county.localeCompare(b.county) || a.code.localeCompare(b.code))
  };
  fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  const count = Object.values(counties).reduce((sum, codes) => sum + Object.keys(codes).length, 0);
  console.log(`Wrote ${path.relative(repoRoot, outputPath)} with ${count} names across ${Object.keys(counties).length} localities; ${unresolved.length} unresolved.`);
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
