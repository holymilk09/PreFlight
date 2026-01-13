const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:3002';
const SCREENSHOT_DIR = path.join(__dirname, '..', 'screenshots');

// Create screenshots directory
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function takeScreenshots() {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const pages = [
    { name: '01-landing', url: '/' },
    { name: '02-login', url: '/login' },
    { name: '03-signup', url: '/signup' },
  ];

  for (const p of pages) {
    console.log(`Capturing ${p.name}...`);
    await page.goto(`${BASE_URL}${p.url}`, { waitUntil: 'networkidle0' });
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, `${p.name}.png`),
      fullPage: false,
    });
  }

  // Try to log in and capture dashboard pages
  const email = process.env.TEST_EMAIL;
  const password = process.env.TEST_PASSWORD;

  if (email && password) {
    console.log('Logging in to capture dashboard...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' });

    await page.type('input[type="email"]', email);
    await page.type('input[type="password"]', password);
    await page.click('button[type="submit"]');

    // Wait for navigation to dashboard
    await page.waitForNavigation({ waitUntil: 'networkidle0' }).catch(() => {});
    await new Promise(r => setTimeout(r, 2000)); // Extra wait for animations

    const dashboardPages = [
      { name: '04-dashboard-overview', url: '/dashboard' },
      { name: '05-dashboard-evaluations', url: '/dashboard/evaluations' },
      { name: '06-dashboard-templates', url: '/dashboard/templates' },
      { name: '07-dashboard-api-keys', url: '/dashboard/api-keys' },
      { name: '08-dashboard-settings', url: '/dashboard/settings' },
    ];

    for (const p of dashboardPages) {
      console.log(`Capturing ${p.name}...`);
      await page.goto(`${BASE_URL}${p.url}`, { waitUntil: 'networkidle0' });
      await new Promise(r => setTimeout(r, 1000)); // Wait for animations
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${p.name}.png`),
        fullPage: false,
      });
    }
  } else {
    console.log('No TEST_EMAIL/TEST_PASSWORD set, skipping dashboard pages');
  }

  await browser.close();
  console.log(`\nScreenshots saved to: ${SCREENSHOT_DIR}`);
}

takeScreenshots().catch(console.error);
