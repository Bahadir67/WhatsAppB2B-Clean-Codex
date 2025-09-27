#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick syntax fix for swarm_orders.py"""

with open('src/core/swarm_orders.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the problematic except block
old_pattern = '''    except Exception as e:
        logger.error(f"Timeframe resolution error: {e}")
        return default_start, default_end, default_label, f"Zaman aralığı çözümleme hatası: {str(e)}"


@functools.lru_cache(maxsize=100)'''

new_pattern = '''    except Exception as e:
        logger.error(f"Timeframe resolution error: {e}")
        return default_start, default_end, default_label, f"Zaman aralığı çözümleme hatası: {str(e)}"


@functools.lru_cache(maxsize=100)'''

if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)

    with open('src/core/swarm_orders.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print('✅ Syntax hatası düzeltildi!')
else:
    print('❌ Pattern bulunamadı')