const BASE_URL = "http://localhost:8000/api";

export const searchWord = async (query: string) => {
    const res = await fetch(`${BASE_URL}/search?q=${encodeURIComponent(query)}`);
    return res.json();
};

export const autocompleteWord = async (prefix: string) => {
    const res = await fetch(`${BASE_URL}/autocomplete?q=${encodeURIComponent(prefix)}`);
    return res.json();
};

export const getWordOfDay = async () => {
    const res = await fetch(`${BASE_URL}/word-of-day`);
    return res.json();
};

export const addWord = async (word: string, meaning: string) => {
    const res = await fetch(`${BASE_URL}/add`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ word, meaning })
    });
    return res.json();
};

export const fetchFromPublicAPI = async (word: string) => {
  try {
    const res = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${word}`);
    const data = await res.json();
    if (!Array.isArray(data)) return null;
    const entry = data[0];
    const meaning = entry.meanings?.[0];
    const def = meaning?.definitions?.[0];
    const ipa = entry.phonetics?.find((p: any) => p.text)?.text ?? '';
    return {
      word: entry.word,
      meaning: def?.definition ?? '',
      ipauk: ipa,
      ipaus: ipa,
      pos: meaning?.partOfSpeech ?? '',
      example: def?.example ?? '',
      level: '',
      synonyms: meaning?.synonyms?.slice(0, 5) ?? []
    };
  } catch { return null; }
};

export const searchYoutube = async (query: string) => {
  try {
    const res = await fetch(`${BASE_URL}/youtube?q=${encodeURIComponent(query)}`);
    return await res.json();
  } catch {
    return { videos: [] };
  }
};

export const searchNews = async (query: string) => {
  try {
    const res = await fetch(`${BASE_URL}/news?q=${encodeURIComponent(query)}`);
    return await res.json();
  } catch {
    return { articles: [] };
  }
};


