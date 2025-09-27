"""HTML generation helpers extracted from the legacy Swarm module."""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Iterable, Optional
def generate_product_html(products, query, html_filename):
    """Generate HTML content for product list"""
    products_count = len(products)
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ürün Listesi - {query}</title>
    <style>
        body {{
            margin: 0;
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(160deg, #1e3c72 0%, #2a5298 45%, #1e3c72 100%);
            color: #1f2933;
        }}

        .page-wrapper {{
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 32px 16px 48px;
        }}

        .container {{
            width: 100%;
            max-width: 860px;
            background: #ffffff;
            border-radius: 24px;
            box-shadow: 0 30px 60px rgba(10, 22, 70, 0.18);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(120deg, rgba(42, 82, 152, 0.95), rgba(30, 60, 114, 0.95));
            color: #f8fafc;
            padding: 36px 40px 28px;
            text-align: left;
        }}

        .header h2 {{
            margin: 0 0 12px;
            font-size: 28px;
            letter-spacing: 0.4px;
        }}

        .header p {{
            margin: 4px 0;
            font-size: 16px;
            opacity: 0.92;
        }}

        .results-meta {{
            display: inline-flex;
            align-items: center;
            gap: 12px;
            padding: 10px 16px;
            border-radius: 999px;
            background: rgba(248, 250, 252, 0.18);
            font-size: 14px;
            margin-top: 14px;
        }}

        .content {{
            padding: 32px 40px 40px;
            background: linear-gradient(180deg, #ffffff 0%, #f5f7fb 100%);
        }}

        .product-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
        }}

        .product {{
            position: relative;
            border-radius: 20px;
            padding: 22px 24px;
            background: #ffffff;
            box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
            transition: transform 0.25s ease, box-shadow 0.25s ease;
            cursor: pointer;
        }}

        .product:hover {{
            transform: translateY(-6px);
            box-shadow: 0 20px 32px rgba(15, 23, 42, 0.12);
        }}

        .product-name {{
            font-weight: 600;
            color: #233876;
            font-size: 18px;
            margin-bottom: 8px;
            line-height: 1.35;
        }}

        .product-code {{
            color: #64748b;
            font-size: 14px;
            letter-spacing: 0.4px;
        }}

        .product-price {{
            margin: 16px 0 10px;
            font-size: 20px;
            font-weight: 700;
            color: #16a34a;
        }}

        .product-stock {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: #0f172a;
            font-size: 13px;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(22, 163, 74, 0.12);
        }}

        .product-stock svg {{
            width: 14px;
            height: 14px;
        }}

        .out-of-stock {{
            background: #f8fafc;
            color: #475569;
        }}

        .out-of-stock .product-price {{
            color: #ef4444;
        }}

        .out-of-stock .product-stock {{
            background: rgba(239, 68, 68, 0.12);
            color: #b91c1c;
        }}

        .out-of-stock .product-stock svg {{
            transform: rotate(45deg);
        }}

        @media (max-width: 640px) {{
            .container {{ border-radius: 18px; }}
            .header {{ padding: 30px 24px; }}
            .content {{ padding: 28px 24px 32px; }}
            .product {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="page-wrapper">
        <div class="container">
            <div class="header">
                <h2>Ürün Kataloğu</h2>
                <p>Arama sonucu: <strong>{query}</strong></p>
                <div class="results-meta">
                    <span>🔍 {len(products)} ürün bulundu</span>
                    <span>🕒 Güncelleme: {datetime.utcnow().strftime('%H:%M')}</span>
                </div>
            </div>

            <div class="content">
                <div class="product-list">
                    {"".join([f'''
                        <div class="product {"out-of-stock" if int(p.get("stock", 0) or 0) <= 0 else ""}" onclick="selectProduct('{p["code"]}', '{p["name"].replace("'", "&apos;")}', {p["price"]})">
                            <div class="product-name">{p["name"]}</div>
                            <div class="product-code">Kod: {p["code"]}</div>
                            <div class="product-price">{p["price"]} TL</div>
                            <div class="product-stock">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="20 6 9 17 4 12" />
                                </svg>
                                {('Stok: ' + str(p["stock"]) + ' adet') if int(p.get("stock", 0) or 0) > 0 else 'Tükendi'}
                            </div>
                        </div>
                    ''' for p in products[:50]])}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        (function() {{
            var returnTimeout;

            function navigateBackToWhatsApp() {{
                if (returnTimeout) {{
                    clearTimeout(returnTimeout);
                }}

                try {{
                    window.close();
                }} catch (error) {{
                    console.log('Window close not permitted');
                }}

                returnTimeout = setTimeout(function() {{
                    if (document.referrer && document.referrer.includes('whatsapp')) {{
                        window.location.href = document.referrer;
                    }} else {{
                        window.location.href = 'whatsapp://';
                        setTimeout(function() {{
                            window.location.href = 'https://wa.me/';
                        }}, 400);
                    }}
                }}, 80);
            }}

            window.addEventListener('pageshow', function() {{
                try {{
                    history.replaceState({{ catalog: true }}, document.title, window.location.href);
                    history.pushState({{ catalog: true }}, document.title, window.location.href);
                }} catch (err) {{
                    console.log('History API unavailable');
                }}
            }});

            window.addEventListener('popstate', function() {{
                navigateBackToWhatsApp();
            }});

            window.returnToWhatsApp = navigateBackToWhatsApp;
        }})();

        function copyToClipboard(text) {{
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                return navigator.clipboard.writeText(text);
            }} else {{
                // Fallback for older browsers
                var textArea = document.createElement("textarea");
                textArea.value = text;
                textArea.style.position = "fixed";
                textArea.style.left = "-999999px";
                textArea.style.top = "-999999px";
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                try {{
                    document.execCommand('copy');
                    return Promise.resolve();
                }} catch (err) {{
                    return Promise.reject(err);
                }} finally {{
                    document.body.removeChild(textArea);
                }}
            }}
        }}

        function selectProduct(code, name, price) {{
            console.log('selectProduct called with:', code, name, price);
            // Create WhatsApp message
            var whatsappMsg = "URUN_SECILDI: " + code + " - " + name + " - " + price + " TL";
            console.log('WhatsApp message:', whatsappMsg);

            // Send via fetch
            fetch('/select-product', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    message: whatsappMsg,
                    sessionId: '{html_filename}',
                    productCode: code,
                    productName: name,
                    productPrice: price
                }})
            }}).then(response => {{
                console.log('Fetch response:', response.status);
                if (response.ok) {{
                    // Success - show overlay
                    console.log('Showing success overlay');
                    showSuccessOverlay();
                }} else {{
                    // Server error
                    console.log('Server error:', response.status);
                    showErrorOverlay();
                }}
            }}).catch(error => {{
                // Network error
                console.log('Network error:', error);
                showErrorOverlay();
            }});
        }}

        function showErrorOverlay() {{
            // Create overlay background
            var overlay = document.createElement('div');
            overlay.style.position = 'fixed';
            overlay.style.top = '0';
            overlay.style.left = '0';
            overlay.style.width = '100%';
            overlay.style.height = '100%';
            overlay.style.backgroundColor = 'rgba(239, 68, 68, 0.8)';
            overlay.style.zIndex = '10000';
            overlay.style.display = 'flex';
            overlay.style.alignItems = 'center';
            overlay.style.justifyContent = 'center';
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.3s ease';

            // Create popup box
            var popup = document.createElement('div');
            popup.style.backgroundColor = '#ffffff';
            popup.style.borderRadius = '18px';
            popup.style.padding = '36px 28px';
            popup.style.maxWidth = '360px';
            popup.style.width = '90%';
            popup.style.textAlign = 'center';
            popup.style.boxShadow = '0 18px 42px rgba(239,68,68,0.3)';
            popup.style.transform = 'scale(0.9)';
            popup.style.transition = 'transform 0.3s ease';

            // Create error icon
            var icon = document.createElement('div');
            icon.innerHTML = '❌';
            icon.style.fontSize = '58px';
            icon.style.marginBottom = '18px';

            // Create title
            var title = document.createElement('h3');
            title.innerHTML = 'Seçim Başarısız';
            title.style.color = '#dc2626';
            title.style.margin = '0 0 18px 0';
            title.style.fontSize = '24px';
            title.style.fontWeight = '700';

            // Create message
            var message = document.createElement('p');
            message.innerHTML = 'Ürün seçimi gönderilemedi. Lütfen tekrar deneyin veya WhatsApp üzerinden devam edin.';
            message.style.color = '#475569';
            message.style.margin = '0';
            message.style.fontSize = '16px';
            message.style.lineHeight = '1.6';

            // Assemble popup
            popup.appendChild(icon);
            popup.appendChild(title);
            popup.appendChild(message);
            overlay.appendChild(popup);

            // Add to page
            document.body.appendChild(overlay);

            // Animate in
            setTimeout(function() {{
                overlay.style.opacity = '1';
                popup.style.transform = 'scale(1)';
            }}, 50);

            // Close on overlay click
            overlay.onclick = function(e) {{
                if (e.target === overlay) {{
                    overlay.style.opacity = '0';
                    popup.style.transform = 'scale(0.9)';
                    setTimeout(function() {{
                        if (document.body.contains(overlay)) {{
                            document.body.removeChild(overlay);
                        }}
                    }}, 300);
                }}
            }};

            setTimeout(function() {{
                overlay.onclick({{ target: overlay }});
            }}, 4000);
        }}

        function showSuccessOverlay() {{
            // Create overlay background
            var overlay = document.createElement('div');
            overlay.style.position = 'fixed';
            overlay.style.top = '0';
            overlay.style.left = '0';
            overlay.style.width = '100%';
            overlay.style.height = '100%';
            overlay.style.backgroundColor = 'rgba(15, 23, 42, 0.68)';
            overlay.style.zIndex = '10000';
            overlay.style.display = 'flex';
            overlay.style.alignItems = 'center';
            overlay.style.justifyContent = 'center';
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.3s ease';

            // Create popup box
            var popup = document.createElement('div');
            popup.style.backgroundColor = '#ffffff';
            popup.style.borderRadius = '18px';
            popup.style.padding = '36px 28px';
            popup.style.maxWidth = '360px';
            popup.style.width = '90%';
            popup.style.textAlign = 'center';
            popup.style.boxShadow = '0 18px 42px rgba(15,23,42,0.26)';
            popup.style.transform = 'scale(0.9)';
            popup.style.transition = 'transform 0.3s ease';

            // Create success icon
            var icon = document.createElement('div');
            icon.innerHTML = '✅';
            icon.style.fontSize = '58px';
            icon.style.marginBottom = '18px';

            // Create title
            var title = document.createElement('h3');
            title.innerHTML = 'Ürün Seçildi!';
            title.style.color = '#1f3d7a';
            title.style.margin = '0 0 18px 0';
            title.style.fontSize = '24px';
            title.style.fontWeight = '700';

            // Create message
            var message = document.createElement('p');
            message.innerHTML = '👆 Geri tuşuna bastığınızda WhatsApp&apos;a dönecek ve bu sekme kapanacak.';
            message.style.color = '#475569';
            message.style.margin = '0';
            message.style.fontSize = '17px';
            message.style.lineHeight = '1.6';

            // Assemble popup
            popup.appendChild(icon);
            popup.appendChild(title);
            popup.appendChild(message);
            overlay.appendChild(popup);

            // Add to page
            document.body.appendChild(overlay);

            // Animate in
            setTimeout(function() {{
                overlay.style.opacity = '1';
                popup.style.transform = 'scale(1)';
            }}, 50);

            // Close on overlay click
            overlay.onclick = function(e) {{
                if (e.target === overlay) {{
                    overlay.style.opacity = '0';
                    popup.style.transform = 'scale(0.9)';
                    setTimeout(function() {{
                        if (document.body.contains(overlay)) {{
                            document.body.removeChild(overlay);
                        }}
                    }}, 300);
                }}
            }};

            setTimeout(function() {{
                overlay.onclick({{ target: overlay }});
            }}, 3500);
        }}
    </script>
</body>
</html>"""
    return html


def generate_order_details_html(orders, whatsapp_number, html_filename, tunnel_url='http://localhost:3005', timeframe_label="Tüm Zamanlar", timeframe_note=None):
    """Generate HTML content for order details with cart view and delete functionality"""
    orders_count = len(orders)
    timeframe_note_block = f"\n                <p class=\"timeframe-note\">{timeframe_note}</p>" if timeframe_note else ""
    empty_state_note = f"\n                    <p class=\"note\">{timeframe_note}</p>" if timeframe_note else ""
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sipariş Detayları</title>
    <style>
        body {{
            margin: 0;
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(160deg, #1e3c72 0%, #2a5298 45%, #1e3c72 100%);
            color: #1f2933;
        }}

        .page-wrapper {{
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 32px 16px 48px;
        }}

        .container {{
            width: 100%;
            max-width: 1000px;
            background: #ffffff;
            border-radius: 24px;
            box-shadow: 0 30px 60px rgba(10, 22, 70, 0.18);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(120deg, rgba(42, 82, 152, 0.95), rgba(30, 60, 114, 0.95));
            color: #f8fafc;
            padding: 36px 40px 28px;
            text-align: left;
        }}

        .header h2 {{
            margin: 0 0 12px;
            font-size: 28px;
            letter-spacing: 0.4px;
        }}

        .header p {{
            margin: 4px 0;
            font-size: 16px;
            opacity: 0.92;
        }}

        .results-meta {{
            display: inline-flex;
            align-items: center;
            gap: 12px;
            padding: 10px 16px;
            border-radius: 999px;
            background: rgba(248, 250, 252, 0.18);
            font-size: 14px;
            margin-top: 14px;
        }}

        .content {{
            padding: 32px 40px 40px;
            background: linear-gradient(180deg, #ffffff 0%, #f5f7fb 100%);
        }}

        .order-list {{
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}

        .order-card {{
            border-radius: 20px;
            padding: 24px;
            background: #ffffff;
            box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
            border: 1px solid #e2e8f0;
        }}

        .order-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid #e2e8f0;
        }}

        .order-number {{
            font-weight: 700;
            color: #1e293b;
            font-size: 18px;
        }}

        .order-status {{
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .status-confirmed {{
            background: rgba(34, 197, 94, 0.12);
            color: #16a34a;
        }}

        .status-cancelled {{
            background: rgba(239, 68, 68, 0.12);
            color: #dc2626;
        }}

        .status-pending {{
            background: rgba(251, 191, 36, 0.12);
            color: #d97706;
        }}

        .order-meta {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
            font-size: 14px;
        }}

        .meta-item {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .meta-label {{
            color: #64748b;
            font-weight: 500;
        }}

        .meta-value {{
            color: #1e293b;
            font-weight: 600;
        }}

        .order-items {{
            margin-bottom: 20px;
        }}

        .item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f1f5f9;
        }}

        .item:last-child {{
            border-bottom: none;
        }}

        .item-info {{
            flex: 1;
        }}

        .item-name {{
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 4px;
        }}

        .item-details {{
            color: #64748b;
            font-size: 13px;
        }}

        .item-price {{
            text-align: right;
            font-weight: 600;
            color: #16a34a;
        }}

        .order-total {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 0;
            border-top: 2px solid #e2e8f0;
            margin-top: 16px;
            font-size: 18px;
            font-weight: 700;
            color: #1e293b;
        }}

        .delete-btn {{
            background: #dc2626;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: background-color 0.2s;
        }}

        .delete-btn:hover {{
            background: #b91c1c;
        }}

        .no-orders {{
            text-align: center;
            padding: 60px 20px;
            color: #64748b;
        }}

        .no-orders h3 {{
            margin: 0 0 12px;
            color: #475569;
        }}

        @media (max-width: 640px) {{
            .container {{ border-radius: 18px; }}
            .header {{ padding: 30px 24px; }}
            .content {{ padding: 28px 24px 32px; }}
            .order-card {{ padding: 20px; }}
            .order-header {{ flex-direction: column; align-items: flex-start; gap: 12px; }}
        }}
    </style>
</head>
<body>
    <div class="page-wrapper">
        <div class="container">
            <div class="header">
                <h2>🛒 Sipariş Detayları</h2>
                <p>Siparişlerinizi görüntüleyin ve yönetin</p>
                <div class="results-meta">
                    <span>📦 {orders_count} sipariş bulundu</span>
                    <span>🕒 Güncelleme: {datetime.utcnow().strftime('%H:%M')}</span>
                </div>
            </div>

            <div class="content">
                {"".join([f'''
                <div class="order-card">
                    <div class="order-header">
                        <div class="order-number">{order['order_number']}</div>
                        <div class="order-status status-{order['status'].lower()}">{order['status']}</div>
                    </div>

                    <div class="order-meta">
                        <div class="meta-item">
                            <div class="meta-label">Tarih</div>
                            <div class="meta-value">{order['created_at']}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">Toplam Tutar</div>
                            <div class="meta-value">{order['total_amount']:.2f} TL</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">Ürün Sayısı</div>
                            <div class="meta-value">{len(order['items'])} adet</div>
                        </div>
                    </div>

                    <div class="order-items">
                        {"".join([f'''
                        <div class="item">
                            <div class="item-info">
                                <div class="item-name">{item['product_name']}</div>
                                <div class="item-details">Kod: {item['product_code']} | Adet: {item['quantity']} | Birim Fiyat: {item['unit_price']:.2f} TL</div>
                            </div>
                            <div class="item-price">{item['total_price']:.2f} TL</div>
                        </div>
                        ''' for item in order['items']])}
                    </div>

                    <div class="order-total">
                        <span>TOPLAM</span>
                        <span>{order['total_amount']:.2f} TL</span>
                    </div>

                    {f'<button class="delete-btn" onclick="confirmDeleteOrder(\'{order["order_number"]}\')">Siparişi İptal Et</button>' if order['status'].upper() != 'CANCELLED' else '<div style="color: #64748b; font-style: italic;">Bu sipariş zaten iptal edilmiş</div>'}
                </div>
                ''' for order in orders]) if orders else f'''
                <div class="no-orders">
                    <h3>Henüz Sipariş Yok</h3>
                    <p>{timeframe_label} için sipariş bulunamadı.</p>{empty_state_note}
                    <p>Ürün araması yaparak yeni sipariş oluşturabilirsiniz.</p>
                </div>
                '''}
            </div>
        </div>
    </div>

    <script>
        function confirmDeleteOrder(orderNumber) {{
            showDeleteConfirmation(orderNumber);
        }}

        function showDeleteConfirmation(orderNumber) {{
            // Create overlay background
            var overlay = document.createElement('div');
            overlay.style.position = 'fixed';
            overlay.style.top = '0';
            overlay.style.left = '0';
            overlay.style.width = '100%';
            overlay.style.height = '100%';
            overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
            overlay.style.zIndex = '10000';
            overlay.style.display = 'flex';
            overlay.style.alignItems = 'center';
            overlay.style.justifyContent = 'center';
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.3s ease';

            // Create popup box
            var popup = document.createElement('div');
            popup.style.backgroundColor = '#ffffff';
            popup.style.borderRadius = '18px';
            popup.style.padding = '32px 28px';
            popup.style.maxWidth = '420px';
            popup.style.width = '90%';
            popup.style.textAlign = 'center';
            popup.style.boxShadow = '0 20px 40px rgba(0,0,0,0.3)';
            popup.style.transform = 'scale(0.9)';
            popup.style.transition = 'transform 0.3s ease';

            // Create warning icon
            var icon = document.createElement('div');
            icon.innerHTML = '⚠️';
            icon.style.fontSize = '48px';
            icon.style.marginBottom = '20px';

            // Create title
            var title = document.createElement('h3');
            title.innerHTML = 'Sipariş İptali Onayı';
            title.style.color = '#dc2626';
            title.style.margin = '0 0 16px 0';
            title.style.fontSize = '22px';
            title.style.fontWeight = '700';

            // Create message
            var message = document.createElement('p');
            message.innerHTML = '<strong>' + orderNumber + '</strong> numaralı siparişi iptal etmek istediğinizden emin misiniz?<br><br>Bu işlem <strong>geri alınamaz</strong> ve sipariş kalıcı olarak iptal edilecektir.';
            message.style.color = '#374151';
            message.style.margin = '0 0 24px 0';
            message.style.fontSize = '16px';
            message.style.lineHeight = '1.6';

            // Create button container
            var buttonContainer = document.createElement('div');
            buttonContainer.style.display = 'flex';
            buttonContainer.style.gap = '12px';
            buttonContainer.style.justifyContent = 'center';

            // Cancel button
            var cancelBtn = document.createElement('button');
            cancelBtn.innerHTML = 'İptal';
            cancelBtn.style.backgroundColor = '#6b7280';
            cancelBtn.style.color = 'white';
            cancelBtn.style.border = 'none';
            cancelBtn.style.padding = '12px 24px';
            cancelBtn.style.borderRadius = '8px';
            cancelBtn.style.cursor = 'pointer';
            cancelBtn.style.fontSize = '16px';
            cancelBtn.style.fontWeight = '600';
            cancelBtn.onclick = function() {{
                overlay.style.opacity = '0';
                popup.style.transform = 'scale(0.9)';
                setTimeout(function() {{
                    if (document.body.contains(overlay)) {{
                        document.body.removeChild(overlay);
                    }}
                }}, 300);
            }};

            // Confirm button
            var confirmBtn = document.createElement('button');
            confirmBtn.innerHTML = 'Evet, İptal Et';
            confirmBtn.style.backgroundColor = '#dc2626';
            confirmBtn.style.color = 'white';
            confirmBtn.style.border = 'none';
            confirmBtn.style.padding = '12px 24px';
            confirmBtn.style.borderRadius = '8px';
            confirmBtn.style.cursor = 'pointer';
            confirmBtn.style.fontSize = '16px';
            confirmBtn.style.fontWeight = '600';
            confirmBtn.onclick = function() {{
                // Close confirmation popup
                overlay.style.opacity = '0';
                popup.style.transform = 'scale(0.9)';
                setTimeout(function() {{
                    if (document.body.contains(overlay)) {{
                        document.body.removeChild(overlay);
                    }}
                }}, 300);
                // Execute delete
                deleteOrder(orderNumber);
            }};

            // Assemble buttons
            buttonContainer.appendChild(cancelBtn);
            buttonContainer.appendChild(confirmBtn);

            // Assemble popup
            popup.appendChild(icon);
            popup.appendChild(title);
            popup.appendChild(message);
            popup.appendChild(buttonContainer);
            overlay.appendChild(popup);

            // Add to page
            document.body.appendChild(overlay);

            // Animate in
            setTimeout(function() {{
                overlay.style.opacity = '1';
                popup.style.transform = 'scale(1)';
            }}, 50);
        }}

        function deleteOrder(orderNumber) {{
            // Show loading message
            showMessage('Sipariş iptal ediliyor...', '#f59e0b', '#fef3c7');

            fetch(window.location.origin + '/delete-order', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    orderNumber: orderNumber,
                    whatsappNumber: '{whatsapp_number}'
                }})
            }}).then(response => {{
                console.log('Delete response status:', response.status);
                return response.json().then(data => ({{
                    status: response.status,
                    data: data
                }}));
            }}).then(result => {{
                if (result.status === 200 && result.data.success) {{
                    showMessage('✅ Sipariş başarıyla iptal edildi!', '#16a34a', '#dcfce7');
                    // Reload the page after 2 seconds
                    setTimeout(() => {{
                        window.location.reload();
                    }}, 2000);
                }} else {{
                    console.log('Delete failed:', result.data);
                    showMessage('❌ Sipariş iptal edilemedi: ' + (result.data.error || 'Bilinmeyen hata'), '#dc2626', '#fef2f2');
                }}
            }}).catch(error => {{
                console.log('Delete network error:', error);
                showMessage('❌ Bağlantı hatası. Lütfen tekrar deneyin.', '#dc2626', '#fef2f2');
            }});
        }}

        function showSuccessMessage(message) {{
            showMessage(message, '#16a34a', '#dcfce7');
        }}

        function showErrorMessage(message) {{
            showMessage(message, '#dc2626', '#fef2f2');
        }}

        function showMessage(message, textColor, bgColor) {{
            var notification = document.createElement('div');
            notification.style.position = 'fixed';
            notification.style.top = '20px';
            notification.style.right = '20px';
            notification.style.backgroundColor = bgColor;
            notification.style.color = textColor;
            notification.style.padding = '16px 20px';
            notification.style.borderRadius = '8px';
            notification.style.boxShadow = '0 10px 25px rgba(0,0,0,0.1)';
            notification.style.zIndex = '10000';
            notification.style.fontWeight = '600';
            notification.style.maxWidth = '400px';
            notification.innerHTML = message;

            document.body.appendChild(notification);

            setTimeout(() => {{
                if (document.body.contains(notification)) {{
                    document.body.removeChild(notification);
                }}
            }}, 4000);
        }}
    </script>
</body>
</html>"""
    return html


def generate_product_cards_html(safe_products):
    """Generate HTML cards for products - separate function to avoid nested f-strings"""
    html_parts = []
    for product in safe_products:
        # Stok durumuna göre badge class'ı belirle
        if product['stock'] > 10:
            badge_class = "stock-available"
            badge_text = "Stokta"
        elif product['stock'] > 0:
            badge_class = "stock-low"
            badge_text = "Stokta"
        else:
            badge_class = "stock-out"
            badge_text = "Tükendi"

        # Stok durumuna göre max değer ve disabled attribute belirle
        max_value = min(product['stock'], 999) if product['stock'] > 0 else 0
        disabled_attr = "disabled" if product['stock'] <= 0 else ""

        card_html = f'''
                    <div class="product-card">
                        <div class="product-header">
                            <div class="product-code">{product['code']}</div>
                            <div class="stock-badge {badge_class}">
                                {badge_text}
                            </div>
                        </div>

                        <div class="product-name">{product['name_html']}</div>

                        <div class="product-price">{product['price']:.2f} TL</div>

                        <div class="quantity-section">
                            <label class="quantity-label">Miktar:</label>
                            <input
                                type="number"
                                class="quantity-input"
                                id="qty-{product['code']}"
                                min="0"
                                max="{max_value}"
                                value="0"
                                {disabled_attr}
                                onchange="updateSummary()"
                            >
                        </div>
                    </div>
                    '''
        html_parts.append(card_html)

    return "".join(html_parts)


def generate_javascript_code(safe_products, html_filename):
    """Generate JavaScript code for multi-product ordering - separate function to avoid nested f-strings"""
    js_parts = []

    # updateSummary function
    js_parts.append("""
        function updateSummary() {
            let totalItems = 0;
            let totalAmount = 0;
""")

    for product in safe_products:
        js_parts.append(f"""
            const qty{product['code_js']} = parseInt(document.getElementById("qty-{product['code']}").value) || 0;
            totalItems += qty{product['code_js']};
            totalAmount += qty{product['code_js']} * {product['price']};
""")

    js_parts.append("""
            document.getElementById("total-items").textContent = totalItems;
            document.getElementById("total-amount").textContent = totalAmount.toFixed(2) + " TL";

            const orderBtn = document.getElementById("order-btn");
            orderBtn.disabled = totalItems === 0;
        }
""")

    # placeOrder function
    js_parts.append("""
        function placeOrder() {
            const orderData = {};
""")

    for product in safe_products:
        js_parts.append(f"""
            const qty{product['code_js']} = parseInt(document.getElementById('qty-{product['code']}').value) || 0;
            if (qty{product['code_js']} > 0) {{
                orderData["{product['code']}"] = {{
                    "product_name": "{product['name_js']}",
                    "quantity": qty{product['code_js']},
                    "unit_price": {product['price']},
                    "total_price": qty{product['code_js']} * {product['price']}
                }};
            }}
""")

    whatsapp_number = html_filename.split('_')[1] if '_' in html_filename else 'unknown'

    js_parts.append(f"""
            if (Object.keys(orderData).length === 0) {{
                alert("Lütfen en az bir ürün için miktar girin.");
                return;
            }}

            const orderBtn = document.getElementById("order-btn");
            orderBtn.disabled = true;
            orderBtn.textContent = "⏳ Sipariş İşleniyor...";

            fetch(window.location.origin + "/place-multi-order", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                    orderData: orderData,
                    whatsappNumber: "{whatsapp_number}"
                }})
            }}).then(response => {{
                return response.json().then(data => {{
                    return {{
                        status: response.status,
                        data: data
                    }};
                }});
            }}).then(result => {{
                if (result.status === 200 && result.data.success) {{
                    alert("✅ Sipariş başarıyla oluşturuldu!\\n\\nSipariş No: " + result.data.orderNumber);
                    window.location.reload();
                }} else {{
                    alert("❌ Sipariş oluşturulamadı: " + (result.data.error || "Bilinmeyen hata"));
                    orderBtn.disabled = false;
                    orderBtn.textContent = "🛒 Sipariş Ver";
                }}
            }}).catch(error => {{
                console.log("Order error:", error);
                alert("❌ Bağlantı hatası. Lütfen tekrar deneyin.");
                orderBtn.disabled = false;
                orderBtn.textContent = "🛒 Sipariş Ver";
            }});
        }}

        updateSummary();
""")

    return "".join(js_parts)


def generate_multi_product_order_html(products, query_codes, html_filename):
    """Generate HTML content for multi-product ordering interface"""
    from html import escape

    safe_products = []
    for product in products:
        code = str(product.get('code', ''))
        name = product.get('name', '')
        price_value = product.get('price', 0)
        stock_value = product.get('stock', 0)

        try:
            price_number = float(price_value)
        except (TypeError, ValueError):
            price_number = 0.0

        try:
            stock_number = int(stock_value)
        except (TypeError, ValueError):
            stock_number = 0

        code_js = re.sub(r'[^0-9A-Za-z_]', '_', code)
        name_js = name.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
        safe_products.append({
            'code': code,
            'code_js': code_js,
            'name_html': escape(name),
            'name_js': name_js,
            'price': price_number,
            'stock': stock_number
        })

    query_codes_html = escape(str(query_codes))

    products_count = len(safe_products)
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Çoklu Ürün Siparişi</title>
    <style>
        body {{
            margin: 0;
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(160deg, #1e3c72 0%, #2a5298 45%, #1e3c72 100%);
            color: #1f2933;
        }}

        .page-wrapper {{
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 32px 16px 48px;
        }}

        .container {{
            width: 100%;
            max-width: 900px;
            background: #ffffff;
            border-radius: 24px;
            box-shadow: 0 30px 60px rgba(10, 22, 70, 0.18);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(120deg, rgba(42, 82, 152, 0.95), rgba(30, 60, 114, 0.95));
            color: #f8fafc;
            padding: 36px 40px 28px;
            text-align: left;
        }}

        .header h2 {{
            margin: 0 0 12px;
            font-size: 28px;
            letter-spacing: 0.4px;
        }}

        .header p {{
            margin: 4px 0;
            font-size: 16px;
            opacity: 0.92;
        }}

        .content {{
            padding: 32px 40px 40px;
            background: linear-gradient(180deg, #ffffff 0%, #f5f7fb 100%);
        }}

        .product-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 24px;
            margin-bottom: 32px;
        }}

        .product-card {{
            border-radius: 16px;
            padding: 24px;
            background: #ffffff;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
            border: 1px solid #e2e8f0;
        }}

        .product-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }}

        .product-code {{
            font-weight: 700;
            color: #1e293b;
            font-size: 16px;
        }}

        .stock-badge {{
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .stock-available {{
            background: rgba(34, 197, 94, 0.12);
            color: #16a34a;
        }}

        .stock-low {{
            background: rgba(251, 191, 36, 0.12);
            color: #d97706;
        }}

        .stock-out {{
            background: rgba(239, 68, 68, 0.12);
            color: #dc2626;
        }}

        .product-name {{
            font-weight: 600;
            color: #233876;
            font-size: 18px;
            margin-bottom: 12px;
            line-height: 1.4;
        }}

        .product-price {{
            font-size: 20px;
            font-weight: 700;
            color: #16a34a;
            margin-bottom: 16px;
        }}

        .quantity-section {{
            margin-top: 12px;
        }}

        .quantity-label {{
            display: block;
            font-size: 14px;
            color: #64748b;
            margin-bottom: 8px;
        }}

        .quantity-input {{
            width: 100%;
            padding: 12px;
            border: 1px solid #cbd5f5;
            border-radius: 12px;
            font-size: 16px;
            text-align: center;
            transition: border 0.2s ease;
        }}

        .quantity-input:focus {{
            outline: none;
            border-color: #2563eb;
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15);
        }}

        .quantity-input:disabled {{
            background: #f1f5f9;
            color: #94a3b8;
            cursor: not-allowed;
        }}

        .summary-card {{
            background: #0f172a;
            color: #e2e8f0;
            border-radius: 20px;
            padding: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 24px;
        }}

        .summary-title {{
            font-size: 18px;
            font-weight: 600;
        }}

        .summary-value {{
            font-size: 24px;
            font-weight: 700;
        }}

        .summary-grid {{
            display: grid;
            gap: 12px;
        }}

        .summary-item {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}

        .summary-label {{
            font-size: 14px;
            opacity: 0.8;
        }}

        .order-actions {{
            margin-top: 28px;
            display: flex;
            justify-content: flex-end;
        }}

        .order-btn {{
            background: linear-gradient(120deg, #2563eb, #1d4ed8);
            color: white;
            border: none;
            padding: 14px 32px;
            border-radius: 14px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}

        .order-btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            box-shadow: none;
            transform: none;
        }}

        .order-btn:hover:not(:disabled) {{
            transform: translateY(-1px);
            box-shadow: 0 20px 30px rgba(37, 99, 235, 0.25);
        }}
    </style>
</head>
<body>
    <div class="page-wrapper">
        <div class="container">
            <div class="header">
                <h2>🛒 Çoklu Ürün Siparişi</h2>
                <p>Sorgulanan ürünler: {query_codes_html}</p>
                <div style="margin-top: 12px; font-size: 14px; opacity: 0.9;">
                    Miktar girip siparişinizi tamamlayın
                </div>
            </div>

            <div class="content">
                <div class="product-grid">
                    {generate_product_cards_html(safe_products)}
                </div>

                <div class="summary-card">
                    <div class="summary-title">📊 Sipariş Özeti</div>
                    <div class="summary-grid">
                        <div class="summary-item">
                            <div class="summary-label">Toplam Ürün</div>
                            <div class="summary-value" id="total-items">0</div>
                        </div>
                        <div class="summary-item">
                            <div class="summary-label">Toplam Tutar</div>
                            <div class="summary-value" id="total-amount">0.00 TL</div>
                        </div>
                    </div>
                </div>

                <div class="order-actions">
                    <button class="order-btn" onclick="placeOrder()" id="order-btn">
                        🛒 Sipariş Ver
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
        {generate_javascript_code(safe_products, html_filename)}
    </script>
</body>
</html>"""
    return html


def generate_order_history_html(orders, whatsapp_number, html_filename, timeframe_label="Tüm Zamanlar", timeframe_note=None):
    """Generate HTML content for order history table"""
    orders_count = len(orders)
    timeframe_note_block = f"\n                <p class=\"timeframe-note\">{timeframe_note}</p>" if timeframe_note else ""
    empty_state_note = f"\n                    <p class=\"note\">{timeframe_note}</p>" if timeframe_note else ""
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sipariş Geçmişi</title>
    <style>
        body {{
            margin: 0;
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(160deg, #1e3c72 0%, #2a5298 45%, #1e3c72 100%);
            color: #1f2933;
        }}

        .page-wrapper {{
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 32px 16px 48px;
        }}

        .container {{
            width: 100%;
            max-width: 1000px;
            background: #ffffff;
            border-radius: 24px;
            box-shadow: 0 30px 60px rgba(10, 22, 70, 0.18);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(120deg, rgba(42, 82, 152, 0.95), rgba(30, 60, 114, 0.95));
            color: #f8fafc;
            padding: 36px 40px 28px;
            text-align: left;
        }}

        .header h2 {{
            margin: 0 0 12px;
            font-size: 28px;
            letter-spacing: 0.4px;
        }}

        .header p {{
            margin: 4px 0;
            font-size: 16px;
            opacity: 0.92;
        }}

        .results-meta {{
            display: inline-flex;
            align-items: center;
            gap: 12px;
            padding: 10px 16px;
            border-radius: 999px;
            background: rgba(248, 250, 252, 0.18);
            font-size: 14px;
            margin-top: 14px;
        }}

        .content {{
            padding: 32px 40px 40px;
            background: linear-gradient(180deg, #ffffff 0%, #f5f7fb 100%);
        }}

        .table-container {{
            overflow-x: auto;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            font-size: 14px;
        }}

        thead {{
            background: linear-gradient(120deg, #1e3c72, #2a5298);
            color: white;
        }}

        th {{
            padding: 16px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #e2e8f0;
        }}

        td {{
            padding: 14px 12px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: middle;
        }}

        tbody tr:hover {{
            background: #f8fafc;
        }}

        .order-number {{
            font-weight: 700;
            color: #1e293b;
            font-size: 15px;
        }}

        .status {{
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            display: inline-block;
        }}

        .status-confirmed {{
            background: rgba(34, 197, 94, 0.12);
            color: #16a34a;
        }}

        .status-cancelled {{
            background: rgba(239, 68, 68, 0.12);
            color: #dc2626;
        }}

        .status-draft {{
            background: rgba(251, 191, 36, 0.12);
            color: #d97706;
        }}

        .amount {{
            font-weight: 700;
            color: #16a34a;
            font-size: 15px;
        }}

        .date {{
            color: #64748b;
        }}

        .items-count {{
            color: #475569;
            font-weight: 500;
        }}

        .no-orders {{
            text-align: center;
            padding: 60px 20px;
            color: #64748b;
        }}

        .no-orders h3 {{
            margin: 0 0 12px;
            color: #475569;
        }}

        @media (max-width: 768px) {{
            .container {{ border-radius: 18px; }}
            .header {{ padding: 30px 24px; }}
            .content {{ padding: 28px 24px 32px; }}
            th, td {{ padding: 10px 8px; font-size: 13px; }}
            .order-number {{ font-size: 14px; }}
        }}
    </style>
</head>
<body>
    <div class="page-wrapper">
        <div class="container">
            <div class="header">
                <h2>📋 Sipariş Geçmişi</h2>
                <p>Siparişlerinizin detaylı listesi</p>
                <p class="timeframe-label">🗓️ {timeframe_label}</p>{timeframe_note_block}
                <div class="results-meta">
                    <span>📦 {orders_count} sipariş bulundu</span>
                    <span>🕒 Güncelleme: {datetime.utcnow().strftime('%H:%M')}</span>
                </div>
            </div>

            <div class="content">
                {"".join([f'''
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Sipariş No</th>
                                <th>Tarih</th>
                                <th>Durum</th>
                                <th>Ürün Sayısı</th>
                                <th>Toplam Tutar</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join([f'''
                            <tr>
                                <td><span class="order-number">{order['order_number']}</span></td>
                                <td><span class="date">{order['created_at']}</span></td>
                                <td><span class="status status-{order['status'].lower()}">{order['status_tr']}</span></td>
                                <td><span class="items-count">{order['item_count']} adet</span></td>
                                <td><span class="amount">{order['total_amount']:.2f} TL</span></td>
                            </tr>
                            ''' for order in orders])}
                        </tbody>
                    </table>
                </div>
                ''' for orders_data in [orders]]) if orders else f'''
                <div class="no-orders">
                    <h3>Henüz Sipariş Yok</h3>
                    <p>{timeframe_label} için sipariş bulunamadı.</p>{empty_state_note}
                    <p>Ürün araması yaparak yeni sipariş oluşturabilirsiniz.</p>
                </div>
                '''}
            </div>
        </div>
    </div>
</body>
</html>"""
    return html
