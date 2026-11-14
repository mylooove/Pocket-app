from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
import requests, threading

class EvaluatorApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        self.title = Label(text='POCKET EVALUATOR', font_size=28, bold=True, color=(1,1,1,1))
        self.pair_label = Label(text='USD/CAD', font_size=22, color=(0.8,0.8,0.8,1))
        self.price_label = Label(text='Price: --', font_size=24, bold=True)
        self.signal_label = Label(text='⏳ WAIT', font_size=45, bold=True, color=(1,0.8,0,1))
        self.reason_label = Label(text='Press EVALUATE to check market', font_size=16)
        self.rsi_label = Label(text='RSI: --', font_size=18)
        self.trend_label = Label(text='Trend: --', font_size=18)
        self.fvg_label = Label(text='FVG: --', font_size=18)
        
        self.btn = Button(text='EVALUATE MARKET', font_size=22, background_color=(0,0.7,0,1), size_hint=(1,0.4))
        self.btn.bind(on_press=self.evaluate)
        
        self.layout.add_widget(self.title)
        self.layout.add_widget(self.pair_label)
        self.layout.add_widget(self.price_label)
        self.layout.add_widget(self.signal_label)
        self.layout.add_widget(self.reason_label)
        self.layout.add_widget(self.rsi_label)
        self.layout.add_widget(self.trend_label)
        self.layout.add_widget(self.fvg_label)
        self.layout.add_widget(self.btn)
        
        self.history = []
        self.candles = []
        self.current = None
        self.tick = 0
        # Auto update price every 15 sec
        Clock.schedule_interval(lambda dt: threading.Thread(target=self.update_price).start(), 15)
        return self.layout

    def get_price(self):
        try:
            r = requests.get("https://api.coinbase.com/v2/prices/USD-CAD/spot", timeout=5).json()
            return float(r['data']['amount'])
        except:
            try:
                r = requests.get("https://api.kraken.com/0/public/Ticker?pair=USDCAD", timeout=5).json()
                return float(r['result']['USDCAD']['c'][0])
            except:
                return None

    def calc_rsi(self, prices):
        if len(prices) < 15: return 50
        prices = prices[-15:]
        gains = sum(max(prices[i]-prices[i-1],0) for i in range(1,len(prices)))
        losses = sum(max(prices[i-1]-prices[i],0) for i in range(1,len(prices)))
        if losses == 0: return 100
        rs = (gains/14)/(losses/14)
        return 100 - (100/(1+rs))

    def is_hammer(self, c):
        o,h,l,cl = c
        body = abs(cl-o) or 0.00001
        lower = min(o,cl)-l
        upper = h-max(o,cl)
        return lower > body*1.5 and upper < body*1.5 and lower > 0.00003

    def is_shooting(self, c):
        o,h,l,cl = c
        body = abs(cl-o) or 0.00001
        lower = min(o,cl)-l
        upper = h-max(o,cl)
        return upper > body*1.5 and lower < body*1.5 and upper > 0.00003

    def check_fvg(self, candles):
        if len(candles) < 3: return None
        c1,c2,c3 = candles[-3], candles[-2], candles[-1]
        if c1[1] < c3[2]: return "BULLISH"
        if c1[2] > c3[1]: return "BEARISH"
        return None

    def update_price(self):
        price = self.get_price()
        if price:
            self.history.append(price)
            if len(self.history) > 300: self.history.pop(0)
            self.price_label.text = f"Price: {price:.5f}"
            # Build fake 5-min candles from ticks for demo - in real app uses live candles
            if self.current is None:
                self.current = [price, price, price, price]; self.tick = 1
            else:
                self.current[1] = max(self.current[1], price)
                self.current[2] = min(self.current[2], price)
                self.current[3] = price
                self.tick += 1
                if self.tick >= 20:
                    self.candles.append(self.current)
                    if len(self.candles) > 40: self.candles.pop(0)
                    self.current = None; self.tick = 0

    def evaluate(self, instance):
        price = self.get_price()
        if not price:
            self.reason_label.text = "No internet - check connection"
            return
        self.price_label.text = f"Price: {price:.5f}"
        rsi = self.calc_rsi(self.history) if len(self.history) >= 15 else 50
        fvg = self.check_fvg(self.candles) if len(self.candles) >= 3 else "Collecting..."
        hammer = self.is_hammer(self.candles[-1]) if self.candles else False
        shooting = self.is_shooting(self.candles[-1]) if self.candles else False
        
        self.rsi_label.text = f"RSI: {rsi:.1f}"
        self.fvg_label.text = f"FVG: {fvg}"
        if rsi < 30: self.trend_label.text = "Trend: OVERSOLD - Possible BUY"
        elif rsi > 70: self.trend_label.text = "Trend: OVERBOUGHT - Possible SELL"
        elif hammer: self.trend_label.text = "Trend: Hammer - Reversal Up"
        elif shooting: self.trend_label.text = "Trend: Shooting Star - Reversal Down"
        else: self.trend_label.text = f"Trend: RSI {rsi:.1f}"

        buy_score = 0; sell_score = 0
        reasons = []
        if hammer: buy_score+=1; reasons.append("Hammer")
        if fvg == "BULLISH": buy_score+=1; reasons.append("Bullish FVG")
        if rsi < 30: buy_score+=1; reasons.append("RSI Oversold")
        if shooting: sell_score+=1; reasons.append("Shooting Star")
        if fvg == "BEARISH": sell_score+=1; reasons.append("Bearish FVG")
        if rsi > 70: sell_score+=1; reasons.append("RSI Overbought")

        if buy_score >= 2 and buy_score > sell_score:
            self.signal_label.text = "🟢 BUY"
            self.signal_label.color = (0,1,0,1)
            self.reason_label.text = "BUY: " + " + ".join(reasons)
        elif sell_score >= 2 and sell_score > buy_score:
            self.signal_label.text = "🔴 SELL"
            self.signal_label.color = (1,0,0,1)
            self.reason_label.text = "SELL: " + " + ".join(reasons)
        else:
            self.signal_label.text = "⏳ WAIT"
            self.signal_label.color = (1,0.8,0,1)
            self.reason_label.text = f"WAIT - Need more confirmation. RSI {rsi:.1f} FVG {fvg}"

if __name__ == '__main__':
    EvaluatorApp().run()
