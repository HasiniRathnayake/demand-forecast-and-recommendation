/**
 * Sunrise Super — Unified Dashboard Server
 * Serves all 6 team member dashboards + shared assets
 * Run: node server.js
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3456;
const ROOT = __dirname;

const MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.ico': 'image/x-icon',
    '.svg': 'image/svg+xml',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
};

const server = http.createServer((req, res) => {
    let urlPath = req.url.split('?')[0]; // strip query strings

    // Normalize trailing slash to /index.html
    if (urlPath.endsWith('/')) urlPath += 'index.html';

    // Map routes to file-system paths
    const filePath = path.join(ROOT, urlPath);

    fs.readFile(filePath, (err, data) => {
        if (err) {
            // Try adding .html if no extension
            if (!path.extname(filePath)) {
                const htmlPath = filePath + '.html';
                return fs.readFile(htmlPath, (err2, d2) => {
                    if (err2) {
                        res.writeHead(404, { 'Content-Type': 'text/html' });
                        return res.end(`<h2>404 — Not found: ${urlPath}</h2><p><a href="/">Home</a></p>`);
                    }
                    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
                    res.end(d2);
                });
            }
            res.writeHead(404, { 'Content-Type': 'text/html' });
            return res.end(`<h2>404 — Not found: ${urlPath}</h2><p><a href="/">Home</a></p>`);
        }

        const ext = path.extname(filePath).toLowerCase();
        const ct = MIME[ext] || 'application/octet-stream';
        res.writeHead(200, { 'Content-Type': ct });
        res.end(data);
    });
});

server.listen(PORT, () => {
    console.log('');
    console.log('☀️  Sunrise Super — Unified AI Inventory System');
    console.log('─'.repeat(50));
    console.log(`   Server running at: http://localhost:${PORT}`);
    console.log('');
    console.log('   Dashboards:');
    console.log(`   Home Landing  →  http://localhost:${PORT}/`);
    console.log(`   01 Demand     →  http://localhost:${PORT}/demand-forecasting/`);
    console.log(`   02 Waste      →  http://localhost:${PORT}/waste-monitor/`);
    console.log(`   03 Shipment   →  http://localhost:${PORT}/shipment-detector/`);
    console.log(`   04 Loyalty    →  http://localhost:${PORT}/loyalty-manager/`);
    console.log(`   05 Intake     →  http://localhost:${PORT}/inventory-intake/`);
    console.log(`   06 Procurement→  http://localhost:${PORT}/dashboard/`);
    console.log('');
    console.log('   Press Ctrl+C to stop the server');
    console.log('─'.repeat(50));
});
