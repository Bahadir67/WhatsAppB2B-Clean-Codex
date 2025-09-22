// Configuration loader for Node.js services
const path = require('path');
const dotenv = require('dotenv');

// Load .env from project root
const envPath = path.join(__dirname, '../../.env');
dotenv.config({ path: envPath });

module.exports = {
    env: process.env,
    paths: {
        root: path.join(__dirname, '../..'),
        whatsappSessions: path.join(__dirname, '../../whatsapp-sessions'),
        productPages: path.join(__dirname, '../../product-pages'),
        data: path.join(__dirname, '../../data')
    }
};