"""Flask HTTP surface for the Swarm B2B runtime."""
from __future__ import annotations
import os

from typing import Dict

from flask import Flask, jsonify, request

from swarm_context import get_product_session
from swarm_orders import (
    cancel_order,
    create_order_confirmation_message,
    prepare_multi_order_items,
    save_order,
)
from swarm_runtime import SwarmB2BSystem


# ===================== HTTP SERVER =====================

app = Flask(__name__)
system_instance = None

def get_flask_base_url():
    """Get the base URL for Flask app - use TUNNEL_URL or localhost"""
    tunnel_url = os.getenv('TUNNEL_URL')
    if tunnel_url:
        return tunnel_url.rstrip('/')
    else:
        return "http://localhost:5000"

@app.route('/select-product', methods=['POST'])
def handle_product_selection_web():
    """Handle product selection from HTML page - receive URUN_SECILDI message"""
    global system_instance
    
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400
        
        message = data.get('message', '')
        session_id = data.get('sessionId', '')
        product_code = data.get('productCode', '')
        product_name = data.get('productName', '')
        product_price = data.get('productPrice', '')
        
        if not message or not session_id:
            return jsonify({"error": "message and sessionId required"}), 400
        
        print(f"[SELECT-PRODUCT] Received selection: {message} for session {session_id}")
        
        # Get WhatsApp number from session
        session_data = get_product_session(session_id)
        if not session_data:
            return jsonify({"error": "Session not found or expired"}), 404
        
        whatsapp_number = session_data.get('whatsapp_number')
        if not whatsapp_number:
            return jsonify({"error": "WhatsApp number not found in session"}), 400
        
        print(f"[SELECT-PRODUCT] Processing for WhatsApp: {whatsapp_number}")
        
        # Initialize system if needed
        if system_instance is None:
            print("[SELECT-PRODUCT] Initializing Swarm system...")
            system_instance = SwarmB2BSystem()
        
        # Process the product selection message
        result = system_instance.process_message(message, whatsapp_number)
        
        return jsonify({
            "success": True,
            "response": str(result),
            "whatsapp_number": whatsapp_number,
            "product_code": product_code,
            "session_id": session_id
        })
        
    except Exception as e:
        print(f"[SELECT-PRODUCT Error] {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/process-message', methods=['POST'])
def process_whatsapp_message():
    """WhatsApp mesajlarını işleyen endpoint - TASK 2.5 compatible"""
    global system_instance
    
    try:
        # JSON data al
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400
        
        message = data.get('message', '')
        whatsapp_number = data.get('whatsapp_number', '')
        
        if not message or not whatsapp_number:
            return jsonify({"error": "message and whatsapp_number required"}), 400
        
        print(f"[HTTP] Processing: {message[:50]}... from {whatsapp_number}")
        
        # System instance oluştur (ilk çağrıda)
        if system_instance is None:
            print("[HTTP] Initializing Swarm Single-Product system with TASK 2.5...")
            system_instance = SwarmB2BSystem()
        
        # Swarm sistemini çalıştır
        result = system_instance.process_message(message, whatsapp_number)
        
        return jsonify({
            "success": True,
            "response": str(result),
            "agent_count": 5,
            "message": message[:100],
            "whatsapp_number": whatsapp_number,
            "framework": "OpenAI Swarm Single-Product",
            "workflow": "Cart-Free Instant Ordering",
            "task_2_4": "ÜRÜN_SEÇİLDİ intent enabled",
            "task_2_5": "Enhanced MIKTAR_GİRİŞİ intent implemented"
        })
        
    except Exception as e:
        print(f"[HTTP Error] {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "OK",
        "agents": 5,
        "system": "OpenAI Swarm Single-Product B2B",
        "framework": "Swarm",
        "workflow": "Single-Product Instant Ordering",
        "task_2_4": "ÜRÜN_SEÇİLDİ intent handling",
        "task_2_5": "Enhanced MIKTAR_GİRİŞİ intent processing",
        "conversation_memory": "enabled"
    })

@app.route('/memory-status', methods=['GET'])
def memory_status():
    """Get conversation memory status for debugging"""
    global system_instance

    if system_instance is None:
        return jsonify({"error": "System not initialized"}), 400

    # Get whatsapp_number from query params if provided
    whatsapp_number = request.args.get('whatsapp_number')

    try:
        status = system_instance.get_memory_status(whatsapp_number)
        return jsonify({
            "success": True,
            "memory_status": status
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/clear-memory', methods=['POST'])
def clear_memory():
    """Clear conversation memory for specific user or all users"""
    global system_instance

    if system_instance is None:
        return jsonify({"error": "System not initialized"}), 400

    try:
        data = request.json or {}
        whatsapp_number = data.get('whatsapp_number')

        if whatsapp_number:
            # Clear specific user
            if whatsapp_number in system_instance.conversation_memory:
                del system_instance.conversation_memory[whatsapp_number]
                return jsonify({
                    "success": True,
                    "message": f"Memory cleared for {whatsapp_number}"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": f"No memory found for {whatsapp_number}"
                })
        else:
            # Clear all memory
            count = len(system_instance.conversation_memory)
            system_instance.conversation_memory.clear()
            return jsonify({
                "success": True,
                "message": f"All memory cleared ({count} conversations)"
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/cancel-order-endpoint', methods=['POST'])
def cancel_order_endpoint():
    """Cancel order endpoint called by product-list-server"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "JSON data required"}), 400

        order_number = data.get('orderNumber', '')
        whatsapp_number = data.get('whatsappNumber', '')

        if not order_number or not whatsapp_number:
            return jsonify({"success": False, "error": "orderNumber and whatsappNumber required"}), 400

        print(f"[CANCEL ORDER ENDPOINT] {order_number} for {whatsapp_number}")

        # Use existing cancel_order function
        result = cancel_order(whatsapp_number, order_number)

        print(f"[CANCEL ORDER RESULT] {result}")

        if "İPTAL EDİLDİ" in result or "iptal edildi" in result.lower():
            return jsonify({"success": True, "message": "Sipariş başarıyla iptal edildi"})
        else:
            return jsonify({"success": False, "error": result}), 400

    except Exception as e:
        print(f"[ERROR] cancel_order_endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/place-multi-order', methods=['POST'])
def place_multi_order_endpoint():
    """Place multi-product order from HTML interface"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "JSON data required"}), 400

        order_data = data.get('orderData', {})
        whatsapp_number = data.get('whatsappNumber', '')

        if not order_data or not whatsapp_number:
            return jsonify({"success": False, "error": "orderData and whatsappNumber required"}), 400

        print(f"[MULTI ORDER] {whatsapp_number}: {len(order_data)} products from HTML")

        aggregated_requests: dict[str, int] = {}
        validation_errors: list[str] = []

        for raw_code, item in order_data.items():
            code = str(raw_code).strip().upper()
            if not code:
                validation_errors.append("Ürün kodu eksik")
                continue

            quantity_value = item.get('quantity', 0) if isinstance(item, dict) else 0
            try:
                quantity = int(quantity_value)
            except (TypeError, ValueError):
                validation_errors.append(f"{code or raw_code}: Geçersiz miktar ({quantity_value})")
                continue

            aggregated_requests[code] = aggregated_requests.get(code, 0) + quantity

        validated_items, item_errors, total_amount = prepare_multi_order_items(aggregated_requests)
        validation_errors.extend(item_errors)

        if validation_errors:
            unique_errors = list(dict.fromkeys(validation_errors))
            error_msg = "Sipariş oluşturulamadı:\n" + "\n".join(f"• {error}" for error in unique_errors)
            return jsonify({"success": False, "error": error_msg}), 400

        if not validated_items:
            return jsonify({"success": False, "error": "Geçerli ürün bulunamadı."}), 400

        order_result = save_order(whatsapp_number, validated_items, total_amount)

        if "SIPARIS KAYDEDILDI" in order_result:
            try:
                order_number = order_result.split(":")[1].split("(")[0].strip()
            except (IndexError, AttributeError):
                order_number = ""

            enhanced_message = create_order_confirmation_message(order_number or "BİLİNMİYOR", validated_items, total_amount)

            return jsonify({
                "success": True,
                "orderNumber": order_number,
                "message": enhanced_message,
                "totalAmount": round(float(total_amount), 2)
            })
        else:
            return jsonify({"success": False, "error": order_result}), 400

    except Exception as e:
        print(f"[ERROR] place_multi_order_endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/delete-order', methods=['POST'])
def delete_order_endpoint():
    """Delete order endpoint for direct calls (legacy)"""
    return cancel_order_endpoint()
