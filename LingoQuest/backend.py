import sys, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json

sys.path.insert(0, os.path.dirname(__file__))

try:
    from engine import SearchEngine
except ImportError:
    pass

try:  
    from storage import load_dictionary, save_dictionary, normalize_entry
except ImportError:
    pass

try:
    from utils import resolve_app_file
except ImportError:
    def resolve_app_file(name): return name

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = resolve_app_file("genz_dict.json")
words = load_dictionary(DATA_FILE)
engine = SearchEngine(words)

class AddWordRequest(BaseModel):
    word: str
    meaning: str

@app.get("/api/search")
def search(q: str = ""):
    results = engine.search(q, limit=20)
    out = []
    for r in results:
        out.append({"word": r, **words[r]})
    return {"results": out}

@app.get("/api/autocomplete")
def autocomplete(q: str = ""):
    suggestions = engine.autocomplete(q, limit=10)
    return {"suggestions": suggestions}

@app.get("/api/word-of-day")
def word_of_day():
    try:
        from crud import pick_word_of_day
        w_tuple = pick_word_of_day(words)
        if w_tuple:
            w, entry = w_tuple
            return {"word": w, "entry": entry}
        return {"word": None, "entry": None}
    except ImportError:
        return {"word": None, "entry": None}

@app.post("/api/add")
def add_word(req: AddWordRequest):
    new_entry = normalize_entry({"word": req.word, "meaning": req.meaning})
    words[req.word] = new_entry
    engine.set_words(words)
    save_dictionary(DATA_FILE, words)
    return {"status": "success", "word": req.word, "entry": new_entry}

@app.get("/api/youtube")
def api_youtube(q: str = ""):
    try:
        from youtube_panel import fetch_youtube
        config_file = resolve_app_file("config.json")
        api_key = ""
        try:
            with open(config_file, encoding="utf-8") as f:
                cfg = json.load(f)
                api_key = cfg.get("youtube_api_key", "")
        except:
            pass
        if not api_key:
            return {"videos": []}
        
        videos = fetch_youtube(q, api_key, max_results=4)
        return {"videos": videos}
    except Exception as e:
        return {"videos": [], "error": str(e)}

@app.get("/api/news")
def api_news(q: str = ""):
    try:
        from news_panel import fetch_google_news, decode_google_news_article_url, _extract_google_news_image_url
        import concurrent.futures

        articles = fetch_google_news(q, max_results=5)

        def hydrate(article):
            link = article.get("link", "")
            if link:
                try:
                    resolved = decode_google_news_article_url(link)
                    if resolved:
                        article["resolved_link"] = resolved
                except Exception:
                    resolved = None
                
                if not article.get("image"):
                    try:
                        img = _extract_google_news_image_url(resolved or link)
                        if img:
                            article["image"] = img
                    except Exception:
                        pass
            return article

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            articles = list(executor.map(hydrate, articles))

        return {"articles": articles}
    except Exception as e:
        return {"articles": [], "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
