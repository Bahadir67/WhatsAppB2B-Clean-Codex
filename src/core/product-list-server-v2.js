const express = require('express');
const path = require('path');
const fs = require('fs');
const config = require('./config');

const app = express();
const port = process.env.PRODUCT_SERVER_PORT || 3005;

// Import cleanup service
const HTMLCleanupService = require('./html-cleanup-service');

// Initialize and start cleanup service
const cleanupService = new HTMLCleanupService(config.paths.productPages, 10, 5); // 10 min max age, 5 min interval
cleanupService.start();

// Static files serving
app.use('/products', express.static(config.paths.productPages));
app.use(express.json());

// Filename parsing utility
function parseFilename(filename) {
    try {
        if (!filename.startsWith('products_') || !filename.endsWith('.html')) {
            return null;
        }
        
        const parts = filename.replace('.html', '').split('_');
        
        // Support both legacy format (2 parts) and new format (4 parts)
        if (parts.length === 2) {
            // Legacy format: products_<session>.html
            return {
                whatsappNumber: '905306897885@c.us', // Default fallback
                sessionId: parts[1],
                timestamp: Date.now(),
                legacy: true
            };
        } else if (parts.length === 4) {
            // New format: products_<whatsapp>_<session>_<timestamp>.html
            return {
                whatsappNumber: parts[1] + '@c.us',
                sessionId: parts[2], 
                timestamp: parseInt(parts[3]),
                legacy: false
            };
        } else {
            return null;
        }
    } catch (error) {
        console.error(`[PARSE ERROR] ${filename}:`, error.message);
        return null;
    }
}

// Root endpoint
app.get('/', (req, res) => {
    res.send(`
        <html>
        <head><title>Product List Server</title></head>
        <body style="font-family: Arial; padding: 40px; text-align: center;">
            <h1>🛍️ WhatsApp B2B Product Server</h1>
            <p>Bu server WhatsApp üzerinden gelen ürün sorgularını işler.</p>
            <p>Ürün listesi linki almak için WhatsApp'tan ürün araması yapın.</p>
            <hr>
            <p>Status: ✅ Aktif | Port: ${process.env.PRODUCT_SERVER_PORT || 3006}</p>
        </body>
        </html>
    `);
});

// MIGRATION: Static file serving endpoint (replaces database session endpoint)
app.get('/products/:filename', async (req, res) => {
    try {
        const { filename } = req.params;
        
        // Check if it's a static HTML file request
        if (filename.endsWith('.html') && filename.startsWith('products_')) {
            const filePath = path.join(__dirname, '..', '..', 'product-pages', filename);
            
            // Check if file exists
            if (!fs.existsSync(filePath)) {
                console.error(`[404] File not found: ${filename}`);
                return res.status(404).send(`
                    <html><body>
                        <h2>Ürün listesi bulunamadı</h2>
                        <p>Bu link geçersiz veya süresi dolmuş olabilir.</p>
                        <p>Lütfen yeni bir arama yapın.</p>
                    </body></html>
                `);
            }
            
            // Parse filename for logging
            const parsed = parseFilename(filename);
            if (parsed) {
                console.log(`[ACCESS] ${filename} -> WhatsApp: ${parsed.whatsappNumber}, Session: ${parsed.sessionId}`);
                
                // Check file age (optional warning)
                const ageMinutes = (Date.now() - parsed.timestamp) / (1000 * 60);
                if (ageMinutes > 60) { // Warn if older than 1 hour
                    console.warn(`[OLD FILE] ${filename} is ${Math.round(ageMinutes)} minutes old`);
                }
            }
            
            // Serve the static HTML file
            return res.sendFile(filePath);
        }
        
        // If not HTML file, return 404
        return res.status(404).send(`
            <html><body>
                <h2>Sayfa bulunamadı</h2>
                <p>Geçersiz dosya formatı.</p>
            </body></html>
        `);
        
    } catch (error) {
        console.error('[SERVER ERROR]', error);
        res.status(500).send('Sunucu hatası');
    }
});

// Product selection endpoint - UPDATED for filename parsing
app.post('/select-product', express.json(), async (req, res) => {
    try {
        const { sessionId, message, productCode, productName, productPrice } = req.body;
        
        if (!sessionId || !message || !productCode) {
            return res.json({ success: false, error: 'Session ID, message ve productCode gerekli' });
        }
        
        // Create product object from separate fields
        const product = {
            code: productCode,
            name: productName,
            price: productPrice
        };
        
        console.log(`[PRODUCT SELECTION] ${product.code} from ${sessionId}`);
        
        // MIGRATION: Parse filename to get WhatsApp number (instead of database query)
        let whatsappNumber;
        
        if (sessionId.startsWith('products_') && sessionId.endsWith('.html')) {
            // New filename format
            const parsed = parseFilename(sessionId);
            if (parsed) {
                whatsappNumber = parsed.whatsappNumber;
                console.log(`[FILENAME PARSE] Extracted WhatsApp: ${whatsappNumber}`);
            } else {
                console.error(`[PARSE ERROR] Could not parse filename: ${sessionId}`);
                return res.json({ success: false, error: 'Invalid session format' });
            }
        } else {
            // Legacy fallback (shouldn't happen with new system)
            console.warn(`[LEGACY] Session ID not a filename: ${sessionId}`);
            whatsappNumber = '905306897885@c.us'; // Default fallback
        }
        
        // Convert HTML product selection to ÜRÜN_SEÇİLDİ format for Swarm system
        // Use URUN_SECILDI instead of ÜRÜN_SEÇİLDİ to avoid encoding issues
        const urunSeciidiMessage = `URUN_SECILDI: ${product.code} - ${product.name} - ${product.price} TL`;
        console.log(`[FORMAT CONVERSION] Original: ${message} → URUN_SECILDI: ${urunSeciidiMessage}`);
        
        // Send ÜRÜN_SEÇİLDİ intent to Swarm system
        const axios = require('axios');
        
        try {
            const swarmResponse = await axios.post(`http://localhost:${process.env.SWARM_SERVER_PORT || 3007}/process-message`, {
                message: urunSeciidiMessage,
                whatsapp_number: whatsappNumber
            });
            
            if (swarmResponse.data.success) {
                console.log(`[DEBUG SWARM DATA] ${JSON.stringify(swarmResponse.data, null, 2)}`);
                const responseMessage = swarmResponse.data.response || swarmResponse.data.message || "Ürün seçimi başarılı";
                
                console.log(`[SWARM RESPONSE] ${whatsappNumber}: ${responseMessage.substring(0, 100)}...`);
                console.log(`[SENDING TO WHATSAPP] URL: http://localhost:3001/send-message`);
                console.log(`[SENDING TO WHATSAPP] To: ${whatsappNumber}`);
                console.log(`[SENDING TO WHATSAPP] Message: ${responseMessage.substring(0, 200)}`);
                
                // WhatsApp'a mesaj gönder
                try {
                    const whatsappResponse = await axios.post('http://localhost:3001/send-message', {
                        to: whatsappNumber,
                        message: responseMessage
                    });
                    
                    console.log(`[WHATSAPP RESPONSE] ${JSON.stringify(whatsappResponse.data)}`);
                    console.log(`[WHATSAPP SENT] ${whatsappNumber}: Message sent successfully`);
                } catch (whatsappError) {
                    console.error(`[WHATSAPP ERROR] ${whatsappNumber}:`, whatsappError.message);
                    console.error(`[WHATSAPP ERROR DETAILS]`, whatsappError.response?.data);
                }
                
                res.json({ 
                    success: true, 
                    message: responseMessage,
                    product: product.name,
                    code: product.code
                });
            } else {
                throw new Error(swarmResponse.data.error || 'Swarm system error');
            }
            
        } catch (swarmError) {
            console.error('[SWARM ERROR]', swarmError.message);
            res.json({ 
                success: false, 
                error: 'Swarm sistemi yanıt veremedi: ' + swarmError.message 
            });
        }
        
    } catch (error) {
        console.error('[PRODUCT SELECTION ERROR]', error);
        res.json({ success: false, error: error.message });
    }
});

// Cleanup service management endpoints
app.get('/cleanup/stats', (req, res) => {
    res.json(cleanupService.getStats());
});

app.post('/cleanup/trigger', (req, res) => {
    cleanupService.triggerCleanup();
    res.json({ success: true, message: 'Manual cleanup triggered' });
});

// Health check
app.get('/health', (req, res) => {
    const stats = cleanupService.getStats();
    res.json({ 
        status: 'OK', 
        port: port,
        cleanup_running: stats.isRunning,
        files_cleaned: stats.totalCleaned
    });
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n[SHUTDOWN] Stopping cleanup service...');
    cleanupService.stop();
    console.log('[SHUTDOWN] Server shutting down gracefully');
    process.exit(0);
});

// Generate HTML for product list
function generateProductListHTML(products, query, sessionId) {
    const html = `
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ürün Listesi - ${query}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        .header { text-align: center; margin-bottom: 20px; color: #333; }
        .product { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; background: #fff; }
        .product:hover { background: #f9f9f9; }
        .product-name { font-weight: bold; color: #2c5aa0; margin-bottom: 5px; }
        .product-code { color: #666; font-size: 0.9em; }
        .product-price { color: #d9534f; font-weight: bold; margin: 5px 0; }
        .product-stock { color: #5cb85c; font-size: 0.9em; }
        .select-btn { background: #5cb85c; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
        .select-btn:hover { background: #4cae4c; }
        .out-of-stock { opacity: 0.6; }
        .out-of-stock .select-btn { background: #ccc; cursor: not-allowed; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🛍️ Ürün Listesi</h2>
            <p>Arama: "<strong>${query}</strong>"</p>
            <p>Toplam ${products.length} ürün bulundu</p>
        </div>
        
        ${products.map(product => `
            <div class="product ${product.stock <= 0 ? 'out-of-stock' : ''}">
                <div class="product-name">${product.name}</div>
                <div class="product-code">Kod: ${product.code}</div>
                <div class="product-price">${product.price} TL</div>
                <div class="product-stock">Stok: ${product.stock} adet</div>
                ${product.stock > 0 ? 
                    `<button class="select-btn" onclick="selectProduct('${product.code}', '${product.name}', ${product.price})">Ürünü Seç</button>` :
                    `<button class="select-btn" disabled>Stokta Yok</button>`
                }
            </div>
        `).join('')}
    </div>
    
    <script>
        function selectProduct(code, name, price) {
            const message = "ÜRÜN_SEÇİLDİ: " + code + " - " + name + " - " + price + " TL";
            
            // Try to send to Swarm system
            fetch('/select-product', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: message,
                    sessionId: '${sessionId}',
                    productCode: code,
                    productName: name,
                    productPrice: price
                })
            }).then(response => {
                if (response.ok) {
                    alert('Ürün seçildi! WhatsApp üzerinden devam edin.');
                } else {
                    alert('Seçim başarısız. Lütfen WhatsApp üzerinden devam edin.');
                }
            }).catch(error => {
                console.error('Selection error:', error);
                alert('Ürün seçimi için WhatsApp üzerinden "' + code + '" yazın.');
            });
        }
    </script>
</body>
</html>`;
    
    return html;
}

app.listen(port, () => {
    console.log(`🛍️  Product List Server v2.0 (Dynamic + Static) running on port ${port}`);
    console.log(`📋 URL format: http://localhost:${port}/products/[session_id]`);
    console.log(`🧹 Auto cleanup: ${cleanupService.getStats().config.maxAgeMinutes} min max age`);
    console.log(`✅ PostgreSQL session support enabled`);
});