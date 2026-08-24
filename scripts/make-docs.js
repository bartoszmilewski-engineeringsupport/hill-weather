const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableOfContents, PageBreak, LevelFormat, convertInchesToTwip,
} = require('docx');

const INK = '2A2521', OCHRE = '9A6737', MUTED = '6B6156', RULE = 'DCD2C0';
const MONO = 'Consolas';

// ---------------------------------------------------------------- helpers --
const H1 = (text) => new Paragraph({
  text, heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 160 },
});
const H2 = (text) => new Paragraph({
  text, heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 120 },
});
const H3 = (text) => new Paragraph({
  text, heading: HeadingLevel.HEADING_3, spacing: { before: 220, after: 100 },
});
const P = (text, opts = {}) => new Paragraph({
  spacing: { after: 120, line: 276 },
  children: [new TextRun({ text, ...opts })],
});
// Runs let one paragraph mix bold/code/plain without \n.
const Rich = (runs) => new Paragraph({
  spacing: { after: 120, line: 276 },
  children: runs.map(r => new TextRun(r)),
});
const Code = (lines) => lines.map((l, i) => new Paragraph({
  spacing: { after: i === lines.length - 1 ? 140 : 0, line: 240 },
  shading: { type: ShadingType.CLEAR, fill: 'F4F1EA' },
  indent: { left: convertInchesToTwip(0.2) },
  children: [new TextRun({ text: l || ' ', font: MONO, size: 18 })],
}));
const Bullet = (text) => new Paragraph({
  text, numbering: { reference: 'bullets', level: 0 },
  spacing: { after: 60, line: 276 },
});
const Note = (text) => new Paragraph({
  spacing: { before: 100, after: 160, line: 276 },
  indent: { left: convertInchesToTwip(0.2) },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: OCHRE, space: 12 } },
  children: [new TextRun({ text, italics: true, color: MUTED })],
});

function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (text, opts = {}) => new TableCell({
    width: { size: opts.w, type: WidthType.DXA },
    shading: opts.head ? { type: ShadingType.CLEAR, fill: 'EFEAE0' } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      spacing: { after: 0 },
      children: [new TextRun({
        text: String(text), bold: !!opts.head, size: 19,
        font: opts.mono ? MONO : undefined,
      })],
    })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) => cell(h, { head: true, w: widths[i] })),
      }),
      ...rows.map(r => new TableRow({
        children: r.map((c, i) => cell(c, { w: widths[i], mono: i === 0 && r.mono })),
      })),
    ],
  });
}

const W = [2100, 6900];        // two-column tables, 9000 dxa content width
const W3 = [2600, 3200, 3200];
const W4 = [3000, 2000, 2000, 2000];

// ------------------------------------------------------------------ body --
const body = [];

// Title page
body.push(new Paragraph({
  spacing: { before: 2400, after: 0 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: 'Hill Weather', bold: true, size: 72, color: INK })],
}));
body.push(new Paragraph({
  spacing: { before: 160, after: 0 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'CLOUD BASE AND INVERSIONS FOR BRITISH HILLS',
    size: 22, color: OCHRE, characterSpacing: 60 })],
}));
body.push(new Paragraph({
  spacing: { before: 600, after: 0 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({
    text: 'Technical documentation, developer guide and disaster recovery',
    size: 26, color: MUTED, italics: true })],
}));
body.push(new Paragraph({
  spacing: { before: 1200, after: 0 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: 'hillweather.co.uk', size: 22, color: MUTED })],
}));
body.push(new Paragraph({
  spacing: { before: 80 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: '24 August 2026', size: 22, color: MUTED })],
}));
body.push(new Paragraph({ children: [new PageBreak()] }));

// Contents
body.push(H1('Contents'));
// Word expands the TOC field at update time, so an explicit page break after
// it lands after the expansion and leaves a blank page. Break before the next
// heading instead, which is stable whatever length the contents grows to.
body.push(new TableOfContents('Contents', {
  hyperlink: true, headingStyleRange: '1-2',
}));

// ------------------------------------------------------------ 1. Overview --
body.push(new Paragraph({
  text: '1. What this is', heading: HeadingLevel.HEADING_1,
  pageBreakBefore: true, spacing: { before: 360, after: 160 },
}));
body.push(P('Hill Weather is a free, non-commercial forecast that answers one question no mainstream weather app answers: will the summit be in cloud, above it, or clear?'));
body.push(P('It covers 546 hills across three regions, rebuilt twice daily, and is served as static files. There are no accounts, no advertising and no database.'));

body.push(table(['Thing', 'Value'], [
  ['Live at', 'https://hillweather.co.uk (since 22 August 2026)'],
  ['Coverage', '282 Munros, 214 Wainwrights, 50 Snowdonia Hewitts'],
  ['Code', 'github.com/bartoszmilewski-engineeringsupport/hill-weather'],
  ['Production', 'IONOS VPS, /opt/hillweather, behind Cloudflare'],
  ['Working copy', 'C:\\dev\\hill-weather (never in Google Drive: Drive corrupts .git)'],
  ['Weather data', 'Open-Meteo, UK Met Office ukmo_uk_deterministic_2km'],
  ['Hill data', 'Database of British and Irish Hills v18.5, CC BY 4.0'],
  ['Rebuild times', '05:15 and 16:15 UTC'],
], W));

body.push(H2('1.1 The idea in one paragraph'));
body.push(P('Cloud has a bottom. On a typical day the base sits at, say, 700 metres: below that line you can see for miles, above it you are inside a grey nothing. Which side of that line a summit falls on decides whether the day was worth the drive. Weather models describe the ground as a smooth surface and shave about 60 metres off Ben Nevis and 155 metres off Cadair Idris, so an app showing "conditions on the summit" is usually describing a hill several hundred metres shorter than the one you are standing on. This site ignores the model ground level entirely and reads the atmosphere at each summit true surveyed height.'));

body.push(H2('1.2 Two audiences'));
body.push(Bullet('Hillwalkers: will I see anything, and is it safe to be up there? Cloud base against summit height, plus wind gusts.'));
body.push(Bullet('Landscape photographers: where will the light be, and is there an inversion? A light quality score at sunrise and sunset, sun azimuth per hill, and an inversion score.'));

// ------------------------------------------------------- 2. Architecture --
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(H1('2. Architecture'));
body.push(P('Everything is static. Nothing is computed when a visitor arrives, and no phone ever calls the weather API. A scheduler inside the Docker stack rebuilds JSON files twice a day; nginx serves them; the browser renders the page from those files.'));

body.push(...Code([
  '  Open-Meteo API  (UK Met Office 2 km model)',
  '        |',
  '        |  twice daily, 05:15 and 16:15 UTC',
  '        v',
  '  deploy/scheduler.py',
  '        |',
  '        +--> scripts/archive.py    ~60 validation hills, raw responses,',
  '        |                          gzipped, kept forever',
  '        |',
  '        +--> scripts/build.py      all 546 hills, minimal variables',
  '        |         |',
  '        |         +--> scripts/omfetch.py    batched HTTP, backoff on 429',
  '        |         +--> scripts/physics.py    cloud base, verdict, light',
  '        |         +--> scripts/solar.py      sunrise, azimuth, golden hour',
  '        |         +--> scripts/hills.py      DoBIH hill lists',
  '        |         +--> data/sources.json     Wikipedia and route links',
  '        |         v',
  '        |    web/data/<region>/summary.json      (the ranked list)',
  '        |    web/data/<region>/hills/<slug>.json (per hill, on tap)',
  '        |',
  '        +--> scripts/og_image.py   link preview card',
  '        +--> scripts/sitemap.py    sitemap.xml and robots.txt',
  '',
  '  nginx (static)  <---  Nginx Proxy Manager  <---  Cloudflare  <--- browser',
]));

body.push(H2('2.1 Why static'));
body.push(Bullet('One build serves everyone. The free Open-Meteo tier could never survive per-visitor requests.'));
body.push(Bullet('The site works on one bar of signal in a car park, which is where it is actually opened.'));
body.push(Bullet('Nothing to attack. No database, no sessions, no user data.'));

body.push(H2('2.2 The split output'));
body.push(P('Each region produces a small summary plus one file per hill. A single 5.5 MB file was unusable on a slow connection. The summary carries only what the ranked list needs; the hill detail is fetched when a hill is tapped.'));

body.push(table(['File', 'Contains'], [
  ['data/index.json', 'Which regions exist, and where their summaries are'],
  ['<region>/summary.json', 'Every hill: name, height, position, daily verdict, view percentage, cloud base and top, freezing level, inversion and light scores, gust, wind, rain'],
  ['<region>/hills/<slug>.json', 'One hill: everything above plus hourly data, sun times, grid reference, Wikipedia extract and route link'],
], W));

// --------------------------------------------------------- 3. The physics --
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(H1('3. How the weather calculation works'));
body.push(P('This is the heart of the project and lives in scripts/physics.py. Everything else is plumbing.'));

body.push(H2('3.1 Pressure levels, not surface data'));
body.push(P('The site asks Open-Meteo for the atmosphere at eight pressure levels rather than at the ground: 1000, 975, 950, 925, 900, 850, 800 and 700 hPa. For each level it takes temperature, relative humidity, wind speed and direction, and geopotential height, which is the actual altitude of that pressure surface in metres.'));
body.push(P('That gives a vertical profile above each hill. The profile is then interpolated to the summit true height, taken from the surveyed DoBIH figure and not from the model own terrain.'));
body.push(Note('This is the single thing that distinguishes the site. A 2 km model smooths Ben Nevis down by about 60 m and Cadair Idris by 155 m. Reading conditions at the model ground level means describing a mountain that does not exist.'));
body.push(P('Vertical resolution is a real limit: near the ground the levels are about 215 m apart, but between 900 and 850 hPa, exactly where Munro summits sit, the gap is 466 m. Interpolation cannot invent detail that is not there.'));

body.push(H2('3.2 Two estimates of cloud base'));
body.push(H3('The lifting condensation level'));
body.push(P('Air lifted from the glen cools until it saturates. The height at which that happens is the lifting condensation level and it is the base of orographic hill fog, which is the dominant British case.'));
body.push(...Code([
  'LCL = LCL_K * (temperature - dewpoint)     LCL_K = 145 m per degC',
]));
body.push(P('The dewpoint is derived from temperature and relative humidity by the Magnus formula, using the 975 hPa level, roughly 350 m, as representative of glen level air.'));
body.push(Rich([
  { text: 'LCL_K is 145 rather than the textbook 125. ' },
  { text: 'It was chosen by measurement', bold: true },
  { text: ': sweeping it against observed cloud base showed the error bottoming between 140 and 150. See section 6.' },
]));

body.push(H3('The relative humidity profile'));
body.push(P('Walking up the interpolated profile in 25 m steps, the first layer where relative humidity exceeds RH_MOIST (85%) is treated as the cloud base, and the top of that layer as the cloud top. The threshold is 85 rather than 95 because a grid box average is diluted: a box that is genuinely full of cloud rarely averages above 90.'));
body.push(P('Finding the cloud TOP is what makes inversions detectable, and inversions are the reason the site exists for photographers.'));

body.push(H3('Which one wins'));
body.push(P('The LCL is preferred where it sits above a moist boundary layer, because a damp low level airmass is normal and is not itself cloud. Otherwise the humidity profile is used.'));

body.push(H2('3.3 From cloud base to a percentage'));
body.push(P('Two independent things must be true for a summit to be in cloud: there must be cloud, and the summit must be above its base.'));
body.push(...Code([
  'P(in cloud) = P(cloud present) x P(summit above the true base)',
  '',
  '  P(cloud present)   = modelled low cloud cover',
  '  P(above the base)  = normal CDF( (summit - base) / BASE_SIGMA )',
  '',
  'BASE_SIGMA = 500 m',
]));
body.push(Note('This replaced a serious bug. The old code treated the modelled base as exact, with a hard cliff: a hill 51 m below it got a 90% chance of a view and one 49 m below got 5%. On an input whose mean absolute error is about 300 m that is false precision, and because the cliff always fell the pessimistic way the forecast cried wolf. Fixing it took skill against climatology from minus 29% to plus 20.6%.'));
body.push(P('The result is then corrected against what was actually observed, because even after that fix the forecast remained systematically too pessimistic:'));
body.push(...Code([
  'p_calibrated = sigmoid(CALIB_A + CALIB_B * logit(p_raw))',
  '',
  'CALIB_A = -0.237     CALIB_B = 0.834',
]));
body.push(P('These two numbers were fitted on measured observations and take skill from plus 20.6% to plus 26.3%. They are summer numbers and should be refitted once winter data exists.'));

body.push(H2('3.4 Labels'));
body.push(table(['Label', 'When'], [
  ['ABOVE CLOUD', 'Summit more than CLEAR_MARGIN (150 m) above the cloud top. An inversion.'],
  ['JUST ABOVE?', 'Summit above the cloud top but by less than the margin. Genuinely uncertain.'],
  ['CLEAR', 'Calibrated probability of cloud below 25%, so 75% chance of a view or better.'],
  ['ON THE EDGE', 'Between 25% and 60%. In and out.'],
  ['IN CLOUD', 'Above 60%.'],
], W));
body.push(Note('The UI colour thresholds in web/index.html and web/week.html must match these boundaries. They drifted apart once and a hill read "on the edge" in its entry while showing green in the list.'));

body.push(H2('3.5 The daily number'));
body.push(P('The headline percentage is the AVERAGE across 09:00 to 17:00, the hours people are actually on the tops, not the day best hour. Taking the maximum made a hill that sat in cloud all day read as 95%.'));

body.push(H2('3.6 Inversion and light scores'));
body.push(P('The inversion score rewards clearance above the cloud top, weighted by cover and layer depth, so a summit poking 20 m out of a thin layer does not score the same as one standing 400 m above a deep one.'));
body.push(P('The light score is sampled at sunrise and sunset specifically, never maxed across the day, because a good score at midday means nothing. Mid and high cloud count in its favour, since a clear sky gives a bland sunrise; low cloud counts against it, except when you are above it, when it becomes the subject rather than the obstruction.'));

// ------------------------------------------------------------ 4. The code --
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(H1('4. The code'));
body.push(table(['File', 'Does'], [
  ['scripts/physics.py', 'Cloud base, verdict, inversion and light scores. The heart.'],
  ['scripts/hills.py', 'Hill lists from DoBIH, region definitions, height bands.'],
  ['scripts/omfetch.py', 'All Open-Meteo access. Batching, variables, backoff.'],
  ['scripts/solar.py', 'Sunrise, sunset, azimuth, golden and blue hour. NOAA algorithm.'],
  ['scripts/build.py', 'Turns fetched data into the JSON the site reads.'],
  ['scripts/archive.py', 'Stores raw API responses for the validation subset, forever.'],
  ['scripts/sources.py', 'Wikipedia extracts and Walkhighlands links, cached.'],
  ['scripts/validate.py', 'Scores the forecast against observations.'],
  ['scripts/version_assets.py', 'Content hashes on CSS and JS URLs.'],
  ['scripts/sitemap.py', 'sitemap.xml and robots.txt.'],
  ['scripts/og_image.py', 'The link preview card.'],
  ['scripts/screenshots.py', 'README screenshots, headless Chrome.'],
  ['scripts/contact_server.py', 'The only dynamic path on the site.'],
  ['deploy/scheduler.py', 'Runs the pipeline on a schedule inside the stack.'],
], W));

body.push(H2('4.1 Front end'));
body.push(P('Static HTML, one stylesheet, vanilla JavaScript. No framework, no build step.'));
body.push(table(['File', 'Does'], [
  ['web/index.html', 'The forecast. Renders from summary.json; fetches a hill on tap.'],
  ['web/week.html', 'Three days compared: which day rather than which hill.'],
  ['web/how-to-read.html', 'The explainer, including measured reliability.'],
  ['web/contact.html', 'Contact form.'],
  ['web/404.html', 'Real 404, served with a 404 status.'],
  ['web/style.css', 'The whole design system, on CSS custom properties.'],
  ['web/glyph.js', 'Per-hill elevation silhouettes, deterministic from the name.'],
  ['web/share.js', 'The share card, drawn on canvas at 1200 x 630.'],
  ['web/theme.js', 'Light and dark, following the device with a manual override.'],
  ['web/analytics.js', 'Google Analytics, behind consent.'],
], W));

body.push(H2('4.2 Constants that matter'));
body.push(table(['Constant', 'Value', 'Meaning'], [
  ['LCL_K', '145.0', 'Metres of lift per degC of dewpoint depression'],
  ['RH_MOIST', '85.0', 'Relative humidity counted as cloud'],
  ['LOW_CLOUD_MIN', '15.0', 'Below this cover, treated as cloud free'],
  ['CLEAR_MARGIN', '150.0', 'Clearance needed before claiming an inversion'],
  ['BASE_SIGMA', '500.0', 'How well the cloud base is actually known'],
  ['CALIB_A / CALIB_B', '-0.237 / 0.834', 'Fitted correction on the output'],
  ['PARCEL_LEVEL', '975', 'Pressure level used as glen level air'],
  ['GRID', '25', 'Metres, vertical step of the interpolated profile'],
], W3));

// ------------------------------------------------------------ 5. Deploying --
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(H1('5. Running and deploying'));
body.push(H2('5.1 Local'));
body.push(...Code([
  'git clone https://github.com/bartoszmilewski-engineeringsupport/hill-weather',
  'cd hill-weather',
  '',
  'python scripts/hills.py                 # check the hill lists load',
  'python scripts/build.py                 # live build, all 546 hills, ~8 min',
  'python scripts/build.py --region lakes  # one region',
  'python -m http.server 8000 -d web       # then open localhost:8000',
]));
body.push(Note('Python 3.12, standard library only. Pillow is optional and only needed for the link preview image.'));

body.push(H2('5.2 Normal deploy'));
body.push(...Code([
  'cd /opt/hillweather && git pull',
]));
body.push(P('That is the whole deploy for HTML, CSS, JavaScript and data: the web container serves files straight off disk. Then purge Cloudflare.'));

body.push(H2('5.3 When more is needed'));
body.push(table(['If you changed', 'Also run'], [
  ['deploy/scheduler.py or scripts/', 'docker compose -f deploy/docker-compose.yml restart scheduler'],
  ['deploy/nginx.conf', 'docker compose up -d --force-recreate web'],
  ['Anything affecting forecast output', 'A rebuild, see 5.4'],
], W));

body.push(H2('5.4 Forcing a rebuild'));
body.push(...Code([
  'cd /opt/hillweather/deploy && docker compose exec -d scheduler \\',
  '  sh -c \'python3 /app/deploy/scheduler.py --once > /app/web/.once.log 2>&1\'',
  '',
  'tail -f /opt/hillweather/web/.once.log',
]));
body.push(Note('Run it detached. A build can sit in a rate limit backoff for twenty minutes and exec without -d dies with the SSH session. Do not stack manual builds: three inside twenty minutes exhausted the hourly API budget and every build failed for an hour after.'));

body.push(H2('5.5 Verify after any config change'));
body.push(...Code([
  'for h in hillweather.co.uk www.hillweather.co.uk \\',
  '         hillweather.uk www.hillweather.uk; do',
  '  printf "%-26s " "$h"',
  '  curl -s -o /dev/null -L --max-time 20 \\',
  '    -w "final %{http_code} after %{num_redirects} hop(s)\\n" "https://$h/"',
  'done',
]));
body.push(P('Every line should end at https://hillweather.co.uk/ in at most one hop. Many hops means a redirect loop and the site is down.'));

// -------------------------------------------------------- 6. Validation --
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(H1('6. Validation: does it actually work?'));
body.push(P('The forecast is scored against real observations by scripts/validate.py. This is the part most hobby weather sites skip, and skipping it is how a site ships something worse than guessing and never finds out.'));

body.push(H2('6.1 Method'));
body.push(P('Airports measure cloud base every half hour, for free, and report the temperature and dewpoint the LCL formula takes as input alongside the base it is trying to predict. Two sources make a validation set available immediately rather than after a season:'));
body.push(Bullet('Open-Meteo previous-runs API: 60 days of history with pressure levels, from the same model. A different endpoint, so it costs none of the daily forecast budget.'));
body.push(Bullet('Iowa State ASOS archive: historical METAR going back decades.'));
body.push(P('An airport at 7 m is never itself in cloud, so the observed ceiling is treated as truth and imaginary summits are placed above each station: if the ceiling was 800 m then a 1000 m summit was in cloud and a 600 m one was not. That gives a confusion matrix and a calibration curve through the production code path.'));

body.push(...Code([
  'python scripts/validate.py --fetch          # about a minute per station',
  'python scripts/validate.py --score',
  'python scripts/validate.py --sweep BASE_SIGMA',
  'python scripts/validate.py --score --rh 75 --lcl 140   # try a candidate',
]));

body.push(H2('6.2 Results, held out and never used for tuning'));
body.push(table(['Measure', 'Before', 'After'], [
  ['Skill vs climatology', 'minus 29%', 'plus 26.3%'],
  ['Brier score', '0.2019', '0.1081'],
  ['Accuracy', '75.6%', '85.6%'],
  ['Beaten by always saying clear?', 'yes (83.0%)', 'no'],
  ['Says IN CLOUD, right', '39.6%', '56.6%'],
  ['Says CLEAR, right', '95.8%', '92.4%'],
  ['Cloud base within 200 m, low cloud', 'about 63%', 'about 63%'],
], W3));

body.push(H2('6.3 Two traps'));
body.push(Rich([
  { text: 'Brier will walk a forecast into the majority class. ', bold: true },
  { text: 'Sweeping LCL_K, the Brier score improved all the way to 200 while the cloud base error bottomed at 140 to 150 and then climbed to 300 m. Past the optimum a larger value simply makes every forecast more optimistic, which pays when 83% of summit-hours are clear without being any more accurate. Choose LCL_K on base error, the physical measure.' },
]));
body.push(Rich([
  { text: 'A holdout stops being a holdout the moment you choose with it. ', bold: true },
  { text: 'Training preferred BASE_SIGMA 500 while the held-out third kept improving past 650. 500 was taken. The held-out number is only worth having because nothing was selected on it.' },
]));

body.push(H2('6.4 What is still unknown'));
body.push(Bullet('Summer only. Every hour of the data is June to August. Winter, when inversions happen, is untested. The model side is a rolling 60 day window, so re-fetch in late winter.'));
body.push(Bullet('Airfields, not mountains. Air lifted over a summit raises the cloud base, so a hill is a harder case than a runway.'));
body.push(Bullet('The 800 to 1400 m band, where most Munros sit, remains the weakest.'));
body.push(Bullet('A full logistic regression on the same inputs scored plus 32.9%, better than the current plus 26.3%, but it was trained on summer airfields, would encode summer, and cannot explain itself. Revisit with winter data.'));

// --------------------------------------------------- 7. Disaster recovery --
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(H1('7. Disaster recovery'));
body.push(Note('Read this first if the VPS is gone. The short version: almost nothing is irreplaceable, because the code is on GitHub and the forecast rebuilds itself. The one exception is the archive.'));

body.push(H2('7.1 What matters, in order'));
body.push(table(['Asset', 'Where', 'Replaceable?'], [
  ['Source code', 'GitHub', 'Yes, it is the master copy'],
  ['Hill data', 'data/hillcsv.zip, committed', 'Yes, redistributable under CC BY 4.0'],
  ['Wikipedia and route cache', 'data/sources.json, committed', 'Yes, rebuild in about an hour'],
  ['Forecast output', 'web/data on the VPS', 'Yes, one rebuild, about 8 minutes'],
  ['The archive', '/opt/hillweather/archive', 'NO. Past forecasts cannot be re-fetched'],
  ['Secrets', 'deploy/.env, never committed', 'No, must be recreated by hand'],
], W3));

body.push(H2('7.2 Rebuilding from nothing'));
body.push(P('On a clean Ubuntu host with Docker installed:'));
body.push(...Code([
  '# 1. Get the code',
  'sudo mkdir -p /opt/hillweather && cd /opt/hillweather',
  'sudo git clone https://github.com/bartoszmilewski-engineeringsupport/hill-weather .',
  '',
  '# 2. Recreate the secrets, see 7.3',
  'cp deploy/.env.example deploy/.env',
  'nano deploy/.env',
  '',
  '# 3. Restore the archive if you have a copy',
  '#    (deploy/migrate.sh moves it between hosts)',
  '',
  '# 4. Start. RUN_ON_START builds immediately when no forecast exists.',
  'cd deploy && docker compose up -d',
  '',
  '# 5. Watch the first build',
  'docker compose logs -f scheduler',
]));
body.push(P('Then point DNS at the new host and put Cloudflare back in front. The site is live as soon as the first build finishes.'));

body.push(H2('7.3 Secrets that must be recreated by hand'));
body.push(P('deploy/.env is gitignored and holds the only things that cannot be recovered from the repository.'));
body.push(table(['Variable', 'What it is'], [
  ['SMTP_HOST, SMTP_PORT', 'Mail relay for the contact form'],
  ['SMTP_USER, SMTP_PASS', 'Gmail address and an app specific password, not the account password'],
  ['CONTACT_TO', 'Where contact form mail is delivered'],
  ['FORM_SECRET', 'Random string, signs the anti spam token. Any new random value works.'],
  ['RUN_TIMES', 'Rebuild schedule, default 05:15,16:15 UTC'],
], W));
body.push(Note('The Gmail app password must be generated fresh from the Google account if lost. It cannot be read back from anywhere.'));

body.push(H2('7.4 External accounts'));
body.push(table(['Service', 'Holds', 'If lost'], [
  ['GitHub', 'All source code', 'Fatal for history; any clone is a full copy'],
  ['Cloudflare', 'DNS and both domains', 'Domains must be recovered through the registrar'],
  ['Google Analytics', 'Property G-8J78948PTM', 'Create a new property, update web/analytics.js'],
  ['Search Console', 'Domain property, verified by DNS', 'Re-verify'],
  ['Open-Meteo', 'No account, free tier', 'Nothing to recover'],
], W3));

body.push(H2('7.5 The archive is the irreplaceable thing'));
body.push(P('scripts/archive.py stores the raw Open-Meteo response, unmodified, for about 60 validation hills, twice a day, forever. Raw rather than derived: if the site archived its own answers then every change to a constant would invalidate the whole history. Keeping raw model output means any future version of the algorithm can be re-scored against every day ever collected.'));
body.push(P('It grows at roughly 0.36 MB a day, about 130 MB a year. Past forecasts cannot be re-fetched from anywhere at any price. Back it up.'));
body.push(...Code([
  'ssh root@vps "tar czf - /opt/hillweather/archive" > archive-backup.tar.gz',
]));

// ------------------------------------------------------------- 8. Traps --
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(H1('8. Traps, each of which cost real time'));
body.push(P('Every one of these looked like something it was not.'));

const traps = [
  ['nginx.conf needs the container recreated', 'Editing it does nothing. docker compose up -d will not do it either: compose sees an unchanged service definition and leaves the container running. Use --force-recreate.'],
  ['server_name _ is not a catch all', 'It is a name matching no real host. A block receives unmatched traffic only because it is the FIRST block on that port. Adding a server block above it silently steals the default. This took the whole site down: the apex matched nothing, fell through to a www redirect and bounced to itself. Fixed with an explicit default_server.'],
  ['Cloudflare caches redirects for hours', 'A return 301 never reaches the location blocks that set short cache headers, so it ships bare and Cloudflare applies a multi hour default. A cached redirect outlives its own fix. Purge after any redirect mistake.'],
  ['Stale assets look exactly like code bugs', 'A four hour CDN cache on the stylesheet, served against new markup, produced giant icons and a collapsed layout while the origin was entirely correct. Fixed for good with content hashed URLs.'],
  ['Test the hostname you did not touch', 'Adding the www redirect, www was verified and passed while the apex was broken.'],
  ['The API limit that bites is per minute', 'A build two hours after the previous one still hit a 429 on its first request, because the archive stage ends and the build stage starts seven seconds later. The fix is pacing, not fewer hills.'],
  ['A silent build is usually a backoff', 'Not a hang. Check with docker compose exec scheduler ps before assuming the worst.'],
  ['A new region needs a build, not just a pull', 'The code ships with git; the site can only show regions that have data files.'],
  ['Never commit generated files', 'sitemap.xml was tracked and regenerated every build, so the VPS working tree diverged within hours and blocked every git pull.'],
  ['Do not scrape MWIS or Walkhighlands', 'Their words are their own editorial work and both are communities this project depends on. Link, never copy. Wikipedia is the licensed source for prose, with attribution.'],
];
traps.forEach(([title, text], i) => {
  body.push(Rich([
    { text: `${i + 1}. ${title}. `, bold: true },
    { text },
  ]));
});

// -------------------------------------------------------------- 9. Next --
body.push(new Paragraph({ children: [new PageBreak()] }));
body.push(H1('9. Where to take it next'));
body.push(H2('9.1 Highest value'));
body.push(Bullet('Winter validation data. Everything measured so far is summer, and inversions are a winter phenomenon. Re-run validate.py --fetch in late February.'));
body.push(Bullet('Per hill pages. 546 hills with descriptions and sun times exist already but live behind client side state, so search engines see one page. This is the largest available traffic change.'));
body.push(Bullet('Summit observations: the Cairngorm summit weather station, the Lake District Fell Top Assessor, webcams. The only way to learn whether any of this transfers off the airfield.'));
body.push(H2('9.2 Cheap and useful'));
body.push(Bullet('Scottish Corbetts. 222 hills, taking the total to 768. Fits inside the free API tier; Grahams on top would not.'));
body.push(Bullet('Offline caching, so the forecast survives losing signal in a glen.'));
body.push(Bullet('A one tap observation report: what was it actually like up there? Feeds validation and costs nothing per user.'));

body.push(H2('9.3 Rules to hold'));
body.push(Bullet('Phones never call the weather API. One build fetches, everyone reads static files.'));
body.push(Bullet('Do not become a general outdoors app. The moment it grows routes and gear lists it is competing with OS Maps and the reason anyone chose it disappears.'));
body.push(Bullet('Be honest about uncertainty. "Could go either way" is a feature and the thing every other weather app refuses to say.'));

body.push(new Paragraph({
  spacing: { before: 400 },
  border: { top: { style: BorderStyle.SINGLE, size: 12, color: RULE, space: 12 } },
  children: [new TextRun({
    text: 'Hill Weather is a free, non-commercial project. Weather data from Open-Meteo using the UK Met Office 2 km model. Hill data from the Database of British and Irish Hills v18.5, CC BY 4.0. Descriptions from Wikipedia, CC BY-SA 4.0. Routes linked to Walkhighlands, never copied.',
    size: 18, color: MUTED, italics: true })],
}));

// --------------------------------------------------------------- assemble --
const doc = new Document({
  creator: 'Hill Weather',
  title: 'Hill Weather: technical documentation',
  description: 'Developer guide, weather calculation reference and disaster recovery',
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: '\u2022',
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 460, hanging: 240 } } },
      }],
    }],
  },
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 21, color: INK } },
      heading1: { run: { font: 'Calibri', size: 34, bold: true, color: INK } },
      heading2: { run: { font: 'Calibri', size: 26, bold: true, color: OCHRE } },
      heading3: { run: { font: 'Calibri', size: 22, bold: true, color: INK } },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },          // A4
        margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 },
      },
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(process.argv[2], buf);
  console.log('written', process.argv[2], (buf.length / 1024).toFixed(0) + ' kB');
});
