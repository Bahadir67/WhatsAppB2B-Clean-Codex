"""Runtime orchestration for the Swarm B2B system."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
import json

from swarm_config import client
from swarm_agents import intent_analyzer
from swarm_context import (
    detect_multi_product_order,
    detect_quantity_input,
    set_current_whatsapp_number,
)
from swarm_orders import create_multi_product_order
from swarm_orders import handle_product_selection


# ===================== SWARM SYSTEM =====================

class SwarmB2BSystem:
    """OpenAI Swarm Single-Product B2B System with Conversation Memory"""

    def __init__(self):
        self.client = client

        # Conversation Memory System - Store last 5 messages per user, 30-minute timeout, FIFO
        self.conversation_memory = {}  # {whatsapp_number: {"messages": [...], "last_activity": datetime, "timeout_minutes": 30}}
        self.memory_settings = {
            "max_messages": 5,  # Store last 5 messages (FIFO)
            "timeout_minutes": 30,  # 30-minute timeout
            "cleanup_on_message": True,  # Cleanup expired conversations after each message
            "extract_context": True  # Auto-extract search context from messages
        }

        # Auto-extracted context for better continuity
        self.extracted_context = {}  # {whatsapp_number: {"product_type": str, "dimensions": str, "features": []}}


        print("[Swarm] Single-Product B2B System initialized")
        print("Agents: Intent Analyzer -> Customer/Product/Sales/Order")
        print("Workflow: Single-Product Instant Ordering (Cart Removed)")
        print("TASK 2.4: ÜRÜN_SEÇİLDİ intent handling enabled")
        print("TASK 2.5: Enhanced MIKTAR_GİRİŞİ intent implemented")
        print(f"[Memory] Conversation memory enabled: {self.memory_settings['max_messages']} messages, {self.memory_settings['timeout_minutes']}min timeout, FIFO cleanup")

    def cleanup_expired_conversations(self):
        """Cleanup expired conversations based on timeout_minutes"""
        if not self.memory_settings['cleanup_on_message']:
            return

        current_time = datetime.now()
        timeout_delta = timedelta(minutes=self.memory_settings['timeout_minutes'])
        expired_numbers = []

        for whatsapp_number, memory_data in self.conversation_memory.items():
            last_activity = memory_data.get('last_activity')
            if last_activity and (current_time - last_activity) > timeout_delta:
                expired_numbers.append(whatsapp_number)

        # Remove expired conversations
        for number in expired_numbers:
            del self.conversation_memory[number]
            print(f"[Memory] Expired conversation cleanup: {number}")

        if expired_numbers:
            print(f"[Memory] Cleaned up {len(expired_numbers)} expired conversations")

    def extract_search_context(self, message: str, whatsapp_number: str):
        """Auto-extract and accumulate search context from messages"""
        if whatsapp_number not in self.extracted_context:
            self.extracted_context[whatsapp_number] = {
                "product_type": None,
                "dimensions": None,
                "features": [],
                "last_search": None
            }

        context = self.extracted_context[whatsapp_number]
        message_lower = message.lower()

        # Extract product type
        product_types = ["silindir", "valf", "filtre", "regülatör", "şartlandırıcı", "yağlayıcı"]
        for ptype in product_types:
            if ptype in message_lower:
                context["product_type"] = ptype
                context["last_search"] = message
                print(f"[Context] Extracted product type: {ptype}")

        # Extract dimensions (e.g., 100x200, 50x100)
        import re
        dimension_match = re.search(r'(\d+)\s*[xX]\s*(\d+)', message)
        if dimension_match:
            context["dimensions"] = dimension_match.group(0)
            print(f"[Context] Extracted dimensions: {context['dimensions']}")

        # Extract features
        feature_keywords = ["yastıklı", "manyetik", "çift etkili", "tek etkili", "5/2", "3/2", "paslanmaz"]
        for feature in feature_keywords:
            if feature in message_lower and feature not in context["features"]:
                context["features"].append(feature)
                print(f"[Context] Added feature: {feature}")

    def add_message_to_memory(self, whatsapp_number: str, role: str, content: str):
        """Add message to conversation memory with FIFO management and context extraction"""
        current_time = datetime.now()

        # Initialize conversation memory if not exists
        if whatsapp_number not in self.conversation_memory:
            self.conversation_memory[whatsapp_number] = {
                "messages": [],
                "last_activity": current_time
            }

        memory_data = self.conversation_memory[whatsapp_number]
        messages = memory_data["messages"]

        # Auto-extract context from user messages
        if role == "user" and self.memory_settings.get("extract_context", False):
            self.extract_search_context(content, whatsapp_number)

        # Add new message
        new_message = {
            "role": role,
            "content": content,
            "timestamp": current_time.isoformat()
        }
        messages.append(new_message)

        # FIFO: Keep only last max_messages
        max_messages = self.memory_settings['max_messages']
        if len(messages) > max_messages:
            messages[:] = messages[-max_messages:]  # Keep last N messages

        # Update last activity
        memory_data["last_activity"] = current_time

        print(f"[Memory] Added {role} message for {whatsapp_number}, total: {len(messages)}/{max_messages}")

    def get_conversation_history(self, whatsapp_number: str) -> List[Dict[str, str]]:
        """Get conversation history for Swarm client (format: [{"role": str, "content": str}])"""
        if whatsapp_number not in self.conversation_memory:
            return []

        messages = self.conversation_memory[whatsapp_number]["messages"]
        # Convert to Swarm format (remove timestamp)
        swarm_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]

        print(f"[Memory] Retrieved {len(swarm_messages)} messages for {whatsapp_number}")
        return swarm_messages

    def get_memory_status(self, whatsapp_number: str = None) -> Dict[str, Any]:
        """Get memory status for debugging"""
        if whatsapp_number:
            if whatsapp_number in self.conversation_memory:
                memory_data = self.conversation_memory[whatsapp_number]
                return {
                    "user": whatsapp_number,
                    "message_count": len(memory_data["messages"]),
                    "last_activity": memory_data["last_activity"].isoformat(),
                    "age_minutes": (datetime.now() - memory_data["last_activity"]).total_seconds() / 60
                }
            else:
                return {"user": whatsapp_number, "status": "no_memory"}
        else:
            return {
                "total_conversations": len(self.conversation_memory),
                "settings": self.memory_settings,
                "users": list(self.conversation_memory.keys())
            }
    
    def _try_handle_manual_order_history(self, message: str, whatsapp_number: str):
        """Parse assistant JSON responses to fetch order history directly."""
        if not isinstance(message, str):
            return None
        stripped = message.strip()
        if not stripped or stripped[0] not in '{[':
            return None
        try:
            payload = json.loads(stripped)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        if isinstance(payload, dict) and 'start_date' in payload and 'end_date' in payload:
            from swarm_orders import get_order_history
            start_date = payload.get('start_date')
            end_date = payload.get('end_date')
            limit = payload.get('limit')
            try:
                whatsapp_formatted = whatsapp_number if whatsapp_number.endswith('@c.us') else whatsapp_number + '@c.us'
                return get_order_history(whatsapp_formatted, timeframe_text=None, limit=limit, start_date=start_date, end_date=end_date)
            except Exception as exc:
                return f"[ERROR] Tarih aralığı işlenemedi: {exc}"
        return None

    def process_message(self, customer_message: str, whatsapp_number: str) -> str:
        """Ana mesaj işleme fonksiyonu - Conversation Memory enabled"""

        # Cleanup expired conversations first
        self.cleanup_expired_conversations()

        # Keep WhatsApp number accessible to downstream tools
        set_current_whatsapp_number(whatsapp_number)

        print(f"[Swarm] Processing: {customer_message[:50]}... from {whatsapp_number}")

        # Add user message to conversation memory
        self.add_message_to_memory(whatsapp_number, "user", customer_message)

        # Get conversation history for context
        conversation_history = self.get_conversation_history(whatsapp_number)

        # TASK 2.4: ÜRÜN_SEÇİLDİ/URUN_SECILDI mesaj detection
        if customer_message.startswith("ÜRÜN_SEÇİLDİ:") or customer_message.startswith("URUN_SECILDI:"):
            print(f"[TASK 2.4] ÜRÜN_SEÇİLDİ/URUN_SECILDI intent detected: {customer_message[:100]}")
            return handle_product_selection(whatsapp_number, customer_message)

        # Check for multi-product orders BEFORE processing
        is_multi_order, order_data = detect_multi_product_order(customer_message)
        if is_multi_order:
            print(f"[MULTI ORDER] Detected {len(order_data['products'])} products in order request")
            return create_multi_product_order(whatsapp_number, order_data['products'])

        # TASK 2.5: MIKTAR_GİRİŞİ pre-detection for logging
        is_quantity_input, _ = detect_quantity_input(customer_message)
        if is_quantity_input:
            print(f"[TASK 2.5] MIKTAR_GİRİŞİ intent potential: {customer_message[:100]}")

        # If we have conversation history, use it; otherwise start fresh
        if conversation_history:
            # Add current message to the history
            messages_for_swarm = conversation_history + [{"role": "user", "content": f"Customer: {whatsapp_number}\nMessage: {customer_message}"}]
            print(f"[Memory] Using conversation history: {len(conversation_history)} previous messages")
        else:
            # Fresh conversation
            messages_for_swarm = [{"role": "user", "content": f"Customer: {whatsapp_number}\nMessage: {customer_message}"}]
            print(f"[Memory] Fresh conversation started for {whatsapp_number}")

        # Swarm'ı çalıştır - Intent Analyzer ile başla
        try:
            # Get extracted context if available
            extracted_ctx = self.extracted_context.get(whatsapp_number, {})

            response = self.client.run(
                agent=intent_analyzer,
                messages=messages_for_swarm,
                context_variables={
                    "whatsapp_number": whatsapp_number,
                    "extracted_context": extracted_ctx  # Pass accumulated context
                },
                debug=True  # Debug açık - handoff'ları görmek için
            )
            
            # Debug: Tüm mesajları göster
            print(f"[DEBUG] Total messages: {len(response.messages)}")
            for i, msg in enumerate(response.messages[-5:]):  # Son 5 mesaj
                print(f"[DEBUG] Message {i}: role={msg.get('role', 'unknown')}, content={str(msg.get('content', ''))[:200]}")
            
            # Assistant response'unu bul ve memory'ye ekle
            final_message = None
            for msg in reversed(response.messages):
                content = str(msg.get("content", ""))
                # Sadece assistant role'ündeki mesajları kontrol et (tool responses ignore)
                if msg.get("role") == "assistant" and content and content not in ["Product Specialist", "Customer Manager", "Sales Expert", "Intent Analyzer", "Order Manager"]:
                    final_message = content
                    break
            
            # Hiçbir şey bulamazsan son mesajı al
            if not final_message:
                final_message = response.messages[-1]["content"]

            manual_override = self._try_handle_manual_order_history(final_message, whatsapp_number)
            if manual_override:
                final_message = manual_override

            # Add assistant response to conversation memory
            self.add_message_to_memory(whatsapp_number, "assistant", final_message)

            print(f"[Swarm] Final response: {final_message[:100]}...")
            print(f"[Memory] Conversation updated for {whatsapp_number}")

            return final_message
            
        except UnicodeEncodeError as ue:
            print(f"[Unicode Error] Encoding issue at position {ue.start}-{ue.end}")
            # For September orders, directly call the function
            if "eylül" in customer_message.lower() or "september" in customer_message.lower():
                from swarm_orders import get_order_history
                try:
                    # Ensure proper WhatsApp number format
                    whatsapp_formatted = whatsapp_number if "@c.us" in whatsapp_number else whatsapp_number + "@c.us"
                    fallback_msg = get_order_history(whatsapp_formatted, "eylül ayı")
                    self.add_message_to_memory(whatsapp_number, "assistant", fallback_msg)
                    return fallback_msg
                except Exception as e:
                    error_msg = f"Eylül ayı siparişlerinizi getirirken bir hata oluştu. Lütfen tekrar deneyin."
                    self.add_message_to_memory(whatsapp_number, "assistant", error_msg)
                    return error_msg
            else:
                error_msg = "Size daha iyi yardımcı olabilmem için, isterseniz siparişlerinizi farklı bir şekilde sorgulayabilirsiniz."
                self.add_message_to_memory(whatsapp_number, "assistant", error_msg)
                return error_msg
        except Exception as e:
            print(f"[Swarm Error] {e}")
            error_msg = f"Sistem hatası: {str(e)}"
            # Add error to memory too
            self.add_message_to_memory(whatsapp_number, "assistant", error_msg)
            return error_msg

