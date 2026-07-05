from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

DATA_DIR = "data"
TRADES_FILE = os.path.join(DATA_DIR, "dummy_trades.json")


def load_trades() -> List[Dict]:
    """Load trades from the JSON file. Creates the file if not exists."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        return []

    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_trades(trades: List[Dict]) -> None:
    """Save trades list to the JSON file."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    with open(TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2)


def add_active_trade(
    symbol: str,
    option_type: str,
    strike_price: float,
    expiry_date: str,
    buy_price: float,
    quantity: int,
    notes: str = ""
) -> Dict:
    """Log a new open position."""
    trades = load_trades()
    
    trade = {
        "id": uuid.uuid4().hex[:12],
        "symbol": symbol.strip().upper(),
        "option_type": option_type.strip().upper(),
        "strike_price": float(strike_price) if option_type != "STOCK" else 0.0,
        "expiry_date": expiry_date.strip() if option_type != "STOCK" else "—",
        "buy_price": float(buy_price),
        "quantity": int(quantity),
        "buy_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sell_price": None,
        "sell_time": None,
        "status": "ACTIVE",
        "pnl": None,
        "pnl_pct": None,
        "notes": notes.strip()
    }
    
    trades.append(trade)
    save_trades(trades)
    return trade


def close_active_trade(trade_id: str, sell_price: float) -> Optional[Dict]:
    """Sell/Close an active open position and calculate realized P&L."""
    trades = load_trades()
    
    for trade in trades:
        if trade["id"] == trade_id and trade["status"] == "ACTIVE":
            sell_p = float(sell_price)
            buy_p = float(trade["buy_price"])
            qty = int(trade["quantity"])
            
            pnl_val = (sell_p - buy_p) * qty
            pnl_pct_val = (sell_p - buy_p) / buy_p * 100.0 if buy_p > 0 else 0.0
            
            trade["status"] = "CLOSED"
            trade["sell_price"] = sell_p
            trade["sell_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            trade["pnl"] = round(pnl_val, 2)
            trade["pnl_pct"] = round(pnl_pct_val, 2)
            
            save_trades(trades)
            return trade
            
    return None


def delete_trade(trade_id: str) -> bool:
    """Delete a trade by ID."""
    trades = load_trades()
    initial_len = len(trades)
    trades = [t for t in trades if t["id"] != trade_id]
    
    if len(trades) < initial_len:
        save_trades(trades)
        return True
    return False


def get_active_trades() -> List[Dict]:
    """Get all currently active (open) trades."""
    trades = load_trades()
    return [t for t in trades if t["status"] == "ACTIVE"]


def get_closed_trades() -> List[Dict]:
    """Get all closed/completed trades."""
    trades = load_trades()
    return [t for t in trades if t["status"] == "CLOSED"]


def compute_stats() -> Dict:
    """Compute aggregate F&O trading stats for closed trades."""
    closed = get_closed_trades()
    
    total_trades = len(closed)
    if total_trades == 0:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "net_pnl": 0.0,
            "profit_factor": 1.0
        }
        
    wins = [t for t in closed if (t["pnl"] or 0) > 0]
    losses = [t for t in closed if (t["pnl"] or 0) <= 0]
    
    win_rate = len(wins) / total_trades * 100.0
    
    gross_profit = sum(float(t["pnl"] or 0.0) for t in wins)
    gross_loss = sum(abs(float(t["pnl"] or 0.0)) for t in losses)
    net_pnl = sum(float(t["pnl"] or 0.0) for t in closed)
    
    profit_factor = 1.0
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = 99.9  # No losses, excellent factor
        
    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "net_pnl": round(net_pnl, 2),
        "profit_factor": round(profit_factor, 2)
    }
