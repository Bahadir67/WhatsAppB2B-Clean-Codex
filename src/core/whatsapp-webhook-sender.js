const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const express = require('express');
const config = require('./config');

// Express server for receiving replies from Swarm system
const app = express();
app.use(express.json());

// WhatsApp Client oluştur
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: config.paths.whatsappSessions,
        clientId: 'client-one'
    }),
    puppeteer: {
        headless: false,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

// QR kod göster
client.on('qr', (qr) => {
    console.log('QR Kod ile giriş yapın:');
    qrcode.generate(qr, { small: true });
});

// Bağlantı başarılı
client.on('ready', () => {
    console.log('WhatsApp Web bağlantısı başarılı!');
    console.log(`OpenAI Swarm sistem aktif: http://localhost:${process.env.SWARM_SERVER_PORT || 3007}`);
});

// Gelen mesajları dinle ve Swarm sistemine gönder
client.on('message', async (message) => {
    console.log(`[DEBUG] Mesaj alındı - From: ${message.from}, Body: ${message.body}`);
    try {
        const userId = message.from;
        const body = message.body;
        
        // Status check command
        if (body === '/status') {
            const statusMsg = `🤖 *OpenAI Swarm Sistemi Aktif*\n\n` +
                            `📊 5-Agent Multi-Agent System\n` +
                            `🔗 Sistem çalışıyor\n\n` +
                            `Tüm mesajlar Swarm sistemine gönderiliyor.`;
            await client.sendMessage(message.from, statusMsg);
            return;
        }
        
        console.log(`[Swarm] Sending - userId: ${userId}, message: ${body}`);
        
        try {
            // Call OpenAI Swarm 5-Agent system
            const response = await axios.post(`http://localhost:${process.env.SWARM_SERVER_PORT || 3007}/process-message`, {
                message: body,
                whatsapp_number: userId
            });
            
            if (response.data.success) {
                console.log('[DEBUG] Full response data:', JSON.stringify(response.data, null, 2));
                const swarmResponse = response.data.response || response.data.message || "Yanıt alınamadı";
                
                // Check for product list link
                const linkMatch = swarmResponse.match(/URUN LISTESI: (https?:\/\/[^\s]+)/);
                if (linkMatch) {
                    // Format with clickable link
                    const formattedResponse = swarmResponse.replace(
                        linkMatch[0],
                        `📋 *ÜRÜN LİSTESİ:*\n${linkMatch[1]}`
                    );
                    await client.sendMessage(message.from, formattedResponse);
                } else {
                    await client.sendMessage(message.from, swarmResponse);
                }
                
                console.log(`[Swarm Yanıt] ${userId}: ${swarmResponse.substring(0, 100)}...`);
            } else {
                throw new Error(response.data.error || 'Swarm system error');
            }
            
        } catch (error) {
            console.error('[Swarm Error]', error);
            await client.sendMessage(message.from, '❌ Sistem hatası. Lütfen tekrar deneyin.');
        }
        
    } catch (error) {
        console.error('[Hata] Mesaj işlenemedi:', error.message);
        await client.sendMessage(message.from, '❌ Sistem hatası. Lütfen tekrar deneyin.');
    }
});

// Bağlantı kesildi
client.on('disconnected', (reason) => {
    console.log('WhatsApp bağlantısı kesildi:', reason);
});

// Authentication failure
client.on('auth_failure', msg => {
    console.error('AUTHENTICATION HATASI', msg);
});

// Loading screen
client.on('loading_screen', (percent, message) => {
    console.log('LOADING SCREEN', percent, message);
});

// Authenticated
client.on('authenticated', () => {
    console.log('AUTHENTICATED - Kimlik doğrulandı');
});

// Swarm sisteminden gelen yanıtları al ve WhatsApp'a gönder
app.post('/send-message', async (req, res) => {
    console.log('[Swarm POST Alındı]', JSON.stringify(req.body, null, 2));
    
    try {
        let { to, message } = req.body;
        
        if (!to || !message) {
            console.error('[Hata] Eksik parametre:', { to, message });
            return res.status(400).json({ error: 'to ve message gerekli' });
        }
        
        // Debug: message'ın tipini ve içeriğini göster
        console.log('[Debug] Message tipi:', typeof message);
        console.log('[Debug] Message içeriği:', message);
        
        // Handle object message format
        if (typeof message === 'object') {
            message = JSON.stringify(message, null, 2);
        }
        
        const chatId = to.includes('@') ? to : `${to}@c.us`;
        console.log(`[Gönderiliyor] ${chatId}: ${message.substring(0, 50)}...`);
        
        await client.sendMessage(chatId, message);
        console.log(`[✓ WhatsApp'a Gönderildi] ${chatId}`);
        
        res.json({ success: true });
    } catch (error) {
        console.error('[Hata] WhatsApp mesajı gönderilemedi:', error.message);
        res.status(500).json({ error: error.message });
    }
});

// Reply server'ı başlat
const REPLY_PORT = 3001;
app.listen(REPLY_PORT, () => {
    console.log(`WhatsApp Reply Server: http://localhost:${REPLY_PORT}/send-message`);
});

// Client'ı başlat
client.initialize().catch(err => {
    console.error('WhatsApp başlatma hatası:', err);
});

console.log('WhatsApp Web.js başlatılıyor...');
console.log('OpenAI Swarm sistemine bağlanılıyor...');
console.log('Session path:', config.paths.whatsappSessions);
console.log('Puppeteer headless:', false);