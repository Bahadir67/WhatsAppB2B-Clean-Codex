const express = require('express');
const path = require('path');
const fs = require('fs');
const config = require('./config');

function toPositiveInt(value, fallback) {
    const parsed = parseInt(value, 10);
    if (Number.isNaN(parsed) || parsed <= 0) {
        return fallback;
    }

    return parsed;
}

const app = express();
const port = process.env.PRODUCT_SERVER_PORT || 3005;
const retentionMinutes = toPositiveInt(process.env.PRODUCT_PAGE_RETENTION_MINUTES, 60);
const cleanupIntervalMinutes = toPositiveInt(process.env.PRODUCT_PAGE_CLEANUP_INTERVAL_MINUTES, 60);
const whatsappWebhookPort = parseInt(process.env.WHATSAPP_WEBHOOK_PORT, 10) || 3001;
const whatsappWebhookUrl = (process.env.WHATSAPP_WEBHOOK_URL || `http://localhost:${whatsappWebhookPort}`).replace(/\/$/, '');
const defaultWhatsappNumber = process.env.WHATSAPP_PHONE ? `${process.env.WHATSAPP_PHONE}@c.us` : null;

// Import cleanup service
const HTMLCleanupService = require('./html-cleanup-service');

// Initialize and start cleanup service
const cleanupService = new HTMLCleanupService(config.paths.productPages, retentionMinutes, cleanupIntervalMinutes);
cleanupService.start();

// Static files serving
app.use('/products', express.static(config.paths.productPages));
app.use(express.json());

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
            <p>Status: ✅ Aktif | Port: ${port}</p>
            <p>Katalog saklama süresi: ${retentionMinutes} dakika | Temizlik sıklığı: ${cleanupIntervalMinutes} dakika</p>
            <p>Aktif katalogları görmek için <code>/catalogs</code> endpoint'ini kullanın.</p>
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
            const parsed = HTMLCleanupService.parseCatalogFilename(filename);
            if (parsed) {
                console.log(`[ACCESS] ${filename} -> WhatsApp: ${parsed.whatsappNumber}, Session: ${parsed.sessionId}`);

                // Check file age (optional warning)
                if (parsed.timestamp) {
                    const ageMinutes = (Date.now() - parsed.timestamp) / (1000 * 60);
                    if (ageMinutes > retentionMinutes) {
                        console.warn(`[OLD FILE] ${filename} is ${Math.round(ageMinutes)} minutes old`);
                    }
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
            const parsed = HTMLCleanupService.parseCatalogFilename(sessionId);
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
            whatsappNumber = defaultWhatsappNumber;
        }

        if (!whatsappNumber) {
            console.error('[PRODUCT SELECTION] WhatsApp number could not be determined');
            return res.json({ success: false, error: 'WhatsApp numarası belirlenemedi' });
        }
        
        // Convert HTML product selection to ÜRÜN_SEÇİLDİ format for Swarm system
        // Use URUN_SECILDI instead of ÜRÜN_SEÇİLDİ to avoid encoding issues
        const normalizedPrice = String(product.price ?? '').trim();
        const hasTlSuffix = /\bTL$/i.test(normalizedPrice);
        const containsDigit = /\d/.test(normalizedPrice);
        const priceWithCurrency = !normalizedPrice
            ? ''
            : (hasTlSuffix || !containsDigit ? normalizedPrice : `${normalizedPrice} TL`);
        const urunSecildiMessage = `URUN_SECILDI: ${product.code} - ${product.name} - ${priceWithCurrency}`;
        console.log(`[FORMAT CONVERSION] Original: ${message} → URUN_SECILDI: ${urunSecildiMessage}`);
        
        // Send ÜRÜN_SEÇİLDİ intent to Swarm system
        const axios = require('axios');
        
        try {
            const swarmResponse = await axios.post(`http://localhost:${process.env.SWARM_SERVER_PORT || 5000}/process-message`, {
                message: urunSecildiMessage,
                whatsapp_number: whatsappNumber
            });
            
            if (swarmResponse.data.success) {
                console.log(`[DEBUG SWARM DATA] ${JSON.stringify(swarmResponse.data, null, 2)}`);
                const responseMessage = swarmResponse.data.response || swarmResponse.data.message || "Ürün seçimi başarılı";
                
                console.log(`[SWARM RESPONSE] ${whatsappNumber}: ${responseMessage.substring(0, 100)}...`);
                const sendMessageUrl = `${whatsappWebhookUrl}/send-message`;
                console.log(`[SENDING TO WHATSAPP] URL: ${sendMessageUrl}`);
                console.log(`[SENDING TO WHATSAPP] To: ${whatsappNumber}`);
                console.log(`[SENDING TO WHATSAPP] Message: ${responseMessage.substring(0, 200)}`);

                // WhatsApp'a mesaj gönder
                try {
                    const whatsappResponse = await axios.post(sendMessageUrl, {
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

// Order delete endpoint
app.post('/delete-order', express.json(), async (req, res) => {
    try {
        const { orderNumber, whatsappNumber } = req.body;

        if (!orderNumber || !whatsappNumber) {
            return res.json({ success: false, error: 'orderNumber and whatsappNumber required' });
        }

        console.log(`[ORDER DELETE] ${orderNumber} for ${whatsappNumber}`);

        // Call the Swarm system to cancel the order
        const axios = require('axios');

        try {
            const swarmResponse = await axios.post(`http://localhost:${process.env.SWARM_SERVER_PORT || 5000}/cancel-order-endpoint`, {
                orderNumber: orderNumber,
                whatsappNumber: whatsappNumber
            });

            if (swarmResponse.data.success) {
                console.log(`[ORDER DELETE SUCCESS] ${orderNumber}`);
                res.json({ success: true, message: 'Sipariş başarıyla iptal edildi' });
            } else {
                console.log(`[ORDER DELETE FAILED] ${orderNumber}: ${swarmResponse.data.error}`);
                res.json({ success: false, error: swarmResponse.data.error || 'Sipariş iptal edilemedi' });
            }

        } catch (swarmError) {
            console.error('[ORDER DELETE SWARM ERROR]', swarmError.message);
            res.json({
                success: false,
                error: 'Swarm sistemi yanıt vermedi: ' + swarmError.message
            });
        }

    } catch (error) {
        console.error('[ORDER DELETE ERROR]', error);
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

// Catalog inspection endpoint
app.get('/catalogs', async (req, res) => {
    try {
        const files = await cleanupService.listCatalogFiles();
        res.json({
            success: true,
            retentionMinutes,
            cleanupIntervalMinutes,
            totalFiles: files.length,
            files
        });
    } catch (error) {
        console.error('[CATALOG LIST ERROR]', error.message);
        res.status(500).json({ success: false, error: 'Kataloglar listelenemedi: ' + error.message });
    }
});

// Health check
app.get('/health', (req, res) => {
    const stats = cleanupService.getStats();
    res.json({
        status: 'OK',
        port: port,
        cleanup_running: stats.isRunning,
        files_cleaned: stats.totalCleaned,
        last_run_at: stats.lastRunAt,
        last_run_deleted: stats.lastRunDeleted,
        last_run_error: stats.lastRunError
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
function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttribute(value) {
    return escapeHtml(value);
}

function generateProductListHTML(products, query, sessionId) {
    const html = `
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ürün Listesi - ${escapeHtml(query)}</title>
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
            <p>Arama: "<strong>${escapeHtml(query)}</strong>"</p>
            <p>Toplam ${products.length} ürün bulundu</p>
        </div>

        ${products.map(product => {
            const codeValue = product.code ?? '';
            const nameValue = product.name ?? '';
            const priceValue = product.price ?? '';
            const rawPriceString = String(priceValue).trim();
            const numericLike = /^\d+(?:[.,]\d+)?$/.test(rawPriceString);
            const hasCurrency = /\bTL$/i.test(rawPriceString);
            const priceLabel = rawPriceString === ''
                ? 'Fiyat bilgisi yok'
                : (hasCurrency || !numericLike ? rawPriceString : `${rawPriceString} TL`);
            const priceDatasetRaw = hasCurrency
                ? rawPriceString.replace(/\bTL$/i, '').trim()
                : rawPriceString;
            const priceDataset = priceDatasetRaw || priceLabel;
            const stockValue = product.stock ?? '';
            const parsedStock = typeof product.stock === 'number'
                ? product.stock
                : parseInt(product.stock, 10);
            const hasNumericStock = !Number.isNaN(parsedStock);
            const hasStock = hasNumericStock ? parsedStock > 0 : Boolean(stockValue);
            const stockLabel = hasNumericStock
                ? `${parsedStock} adet`
                : String(stockValue || 'Stok bilgisi yok');

            return `
            <div class="product ${hasStock ? '' : 'out-of-stock'}">
                <div class="product-name">${escapeHtml(nameValue)}</div>
                <div class="product-code">Kod: ${escapeHtml(codeValue)}</div>
                <div class="product-price">${escapeHtml(priceLabel)}</div>
                <div class="product-stock">Stok: ${escapeHtml(stockLabel)}</div>
                ${hasStock ?
                    `<button class="select-btn" data-code="${escapeAttribute(codeValue)}" data-name="${escapeAttribute(nameValue)}" data-price="${escapeAttribute(priceDataset)}" data-price-label="${escapeAttribute(priceLabel)}">Ürünü Seç</button>` :
                    `<button class="select-btn" disabled>Stokta Yok</button>`
                }
            </div>`;
        }).join('')}
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const container = document.querySelector('.container');
            if (!container) {
                return;
            }

            container.addEventListener('click', async (event) => {
                const button = event.target.closest('.select-btn');
                if (!button || button.disabled) {
                    return;
                }

                const code = (button.dataset.code || '').trim();
                const name = (button.dataset.name || '').trim();
                const price = (button.dataset.price || '').trim();
                const priceLabel = (button.dataset.priceLabel || '').trim();
                const message = "URUN_SECILDI: " + code + " - " + name + " - " + priceLabel;

                try {
                    const response = await fetch('/select-product', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            message: message,
                            sessionId: '${sessionId}',
                            productCode: code,
                            productName: name,
                            productPrice: price
                        })
                    });

                    const result = await response.json().catch(() => null);
                    if (response.ok && result?.success) {
                        alert('Ürün seçildi! WhatsApp üzerinden devam edin.');
                    } else {
                        alert('Seçim başarısız. Lütfen WhatsApp üzerinden devam edin.');
                    }
                } catch (error) {
                    console.error('Selection error:', error);
                    alert('Ürün seçimi için WhatsApp üzerinden "' + code + '" yazın.');
                }
            });
        });
    </script>
</body>
</html>`;

    return html;
}

// Multi-product order placement endpoint
app.post('/place-multi-order', express.json(), async (req, res) => {
    try {
        const { orderData, whatsappNumber } = req.body;

        console.log(`[MULTI ORDER] Received order request from ${whatsappNumber}:`, JSON.stringify(orderData, null, 2));

        if (!orderData || !whatsappNumber) {
            return res.status(400).json({
                success: false,
                error: 'orderData ve whatsappNumber gerekli'
            });
        }

        // Forward order to Swarm system
        const swarmUrl = `http://localhost:3007/process-message`;
        const swarmPayload = {
            userId: whatsappNumber.replace('@c.us', ''),
            whatsapp_number: whatsappNumber,
            message: `MULTI_ORDER_PLACEMENT: ${JSON.stringify(orderData)}`
        };

        console.log(`[MULTI ORDER] Forwarding to Swarm:`, swarmPayload);

        const swarmResponse = await fetch(swarmUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(swarmPayload)
        });

        if (!swarmResponse.ok) {
            console.error(`[MULTI ORDER] Swarm request failed: ${swarmResponse.status}`);
            return res.status(500).json({
                success: false,
                error: 'Sipariş sistemi hatası'
            });
        }

        const swarmResult = await swarmResponse.json();
        console.log(`[MULTI ORDER] Swarm response:`, swarmResult);

        if (swarmResult.success) {
            // Extract order number from response if available
            const orderNumberMatch = swarmResult.response?.match(/Sipariş No[:\s]*([^\s\n]+)/i);
            const orderNumber = orderNumberMatch ? orderNumberMatch[1] : 'UNKNOWN';

            // Send order confirmation to WhatsApp
            try {
                const whatsappResponse = await fetch(`${whatsappWebhookUrl}/send-message`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        to: whatsappNumber,
                        message: swarmResult.response
                    })
                });

                if (whatsappResponse.ok) {
                    console.log(`[MULTI ORDER] WhatsApp confirmation sent to ${whatsappNumber}`);
                } else {
                    console.error(`[MULTI ORDER] WhatsApp send failed: ${whatsappResponse.status}`);
                }
            } catch (whatsappError) {
                console.error('[MULTI ORDER] WhatsApp error:', whatsappError);
            }

            return res.json({
                success: true,
                orderNumber: orderNumber,
                message: swarmResult.response
            });
        } else {
            return res.status(400).json({
                success: false,
                error: swarmResult.error || 'Sipariş oluşturulamadı'
            });
        }

    } catch (error) {
        console.error('[MULTI ORDER ERROR]', error);
        return res.status(500).json({
            success: false,
            error: 'Sunucu hatası'
        });
    }
});

app.listen(port, () => {
    console.log(`🛍️  Product List Server v2.0 (Dynamic + Static) running on port ${port}`);
    console.log(`📋 URL format: http://localhost:${port}/products/[session_id]`);
    console.log(`🧹 Auto cleanup: ${cleanupService.getStats().config.maxAgeMinutes} min max age`);
    console.log(`✅ PostgreSQL session support enabled`);
});