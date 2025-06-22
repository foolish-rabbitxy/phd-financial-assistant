import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from src.trading.alpaca_client import get_ohlc_bars

def plot_candlestick(symbol: str):
    bars = get_ohlc_bars(symbol)
    if not bars:
        print("No bars to plot.")
        return

    # Format data for plotting
    dates = [bar.t for bar in bars]
    opens = [bar.o for bar in bars]
    highs = [bar.h for bar in bars]
    lows = [bar.l for bar in bars]
    closes = [bar.c for bar in bars]

    # Build candlestick chart
    fig, ax = plt.subplots(figsize=(12, 6))
    for i in range(len(dates)):
        color = 'green' if closes[i] >= opens[i] else 'red'
        ax.plot([dates[i], dates[i]], [lows[i], highs[i]], color='black')  # wick
        ax.add_patch(plt.Rectangle((dates[i], min(opens[i], closes[i])),
                                   width=0.6,
                                   height=abs(closes[i] - opens[i]),
                                   color=color))

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.set_title(f'{symbol.upper()} OHLC Candlestick Chart')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_candlestick("AAPL")
