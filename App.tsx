/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/
import React, { useState, useEffect } from 'react';
import { GeneratedImage, SearchMode, SearchResultItem } from './types';
import { 
  researchTopicForPrompt, 
  generateInfographicImage, 
  editInfographicImage,
} from './services/geminiService';
import Infographic from './components/Infographic';
import Loading from './components/Loading';
import IntroScreen from './components/IntroScreen';
import SearchResults from './components/SearchResults';
import DemoHelloResults from './components/DemoHelloResults';
import { searchWord, autocompleteWord, fetchFromPublicAPI, searchYoutube, searchNews } from './services/dictionaryService';
import { Search, AlertCircle, History, Newspaper, Youtube, Microscope, BookOpen, Compass, Globe, Sun, Moon, CreditCard, ExternalLink, DollarSign, Atom, Download } from 'lucide-react';

const App: React.FC = () => {
  const [showIntro, setShowIntro] = useState(true);
  const [topic, setTopic] = useState('');
  // Aspect ratio is now hardcoded to 16:9 in the service calls
  const [searchMode, setSearchMode] = useState<SearchMode>('ai');
  
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [loadingStep, setLoadingStep] = useState<number>(0);
  const [loadingFacts, setLoadingFacts] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  const [imageHistory, setImageHistory] = useState<GeneratedImage[]>([]);
  const [currentSearchResults, setCurrentSearchResults] = useState<SearchResultItem[]>([]);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [isDemoHello, setIsDemoHello] = useState(false);
  
  const [dictResult, setDictResult] = useState<any>(null);
  const [newsArticles, setNewsArticles] = useState<any[]>([]);
  const [videos, setVideos] = useState<any[]>([]);
  const [backendOffline, setBackendOffline] = useState(false);
  const [ghostText, setGhostText] = useState('');
  const [autocompleteTimer, setAutocompleteTimer] = useState<NodeJS.Timeout | null>(null);
  const [notFoundQuery, setNotFoundQuery] = useState('');
  const [currentSearchWord, setCurrentSearchWord] = useState('');
  const [searchTrigger, setSearchTrigger] = useState(0);
  const [videoError, setVideoError] = useState('');

  useEffect(() => {
    if (!currentSearchWord.trim()) return;

    let newsDone = false;
    let ytDone = false;

    const checkLoading = () => {
       if (newsDone && ytDone && searchMode !== 'ai') {
           setIsLoading(false);
           setIsDemoHello(true);
       }
    };

    fetch(`http://127.0.0.1:8000/api/news?q=${encodeURIComponent(currentSearchWord)}`)
      .then(r => r.json())
      .then(data => {
        console.log("[News API response]", data);
        setNewsArticles(data.articles || []);
      })
      .catch(err => {
        console.error("[News API error]", err);
        setNewsArticles([]);
      })
      .finally(() => {
        newsDone = true;
        checkLoading();
      });

    fetch(`http://127.0.0.1:8000/api/youtube?q=${encodeURIComponent(currentSearchWord)}`)
      .then(r => r.json())
      .then(data => {
        console.log("[YouTube API response]", data);
        if (data.error) {
           setVideoError(data.error);
        } else {
           setVideoError('');
        }
        setVideos(data.videos || []);
      })
      .catch(err => {
        console.error("[YouTube API error]", err);
        setVideoError('Network or Backend Error');
        setVideos([]);
      })
      .finally(() => {
        ytDone = true;
        checkLoading();
      });
  }, [currentSearchWord, searchTrigger]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setTopic(v);
    
    if (autocompleteTimer) clearTimeout(autocompleteTimer);
    if (!v.trim()) {
      setGhostText('');
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const data = await autocompleteWord(v.trim());
        if (data.suggestions && data.suggestions.length > 0) {
          setGhostText(data.suggestions[0]);
        } else {
          setGhostText('');
        }
      } catch (err) {
        setGhostText('');
      }
    }, 300);
    setAutocompleteTimer(timer);
  };

  const handleModeSwitch = (mode: SearchMode) => {
    setSearchMode(mode);
    setImageHistory([]);
    setCurrentSearchResults([]);
    setError(null);
  };

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;

    if (!topic.trim()) {
        setError("Please enter a topic to search.");
        return;
    }

    setIsDemoHello(false);
    setImageHistory([]);
    setCurrentSearchResults([]);
    setError(null);
    setDictResult(null);
    setVideos([]);
    setNewsArticles([]);
    setNotFoundQuery('');
    setBackendOffline(false);
    setGhostText('');
    setVideoError('');

    const query = topic.trim();
    setCurrentSearchWord(query);
    setSearchTrigger(prev => prev + 1);

    if (searchMode === 'video' || searchMode === 'news') {
      setIsLoading(true);
      setLoadingStep(1);
      setLoadingMessage(searchMode === 'video' ? 'Đang tìm kiếm video YouTube...' : 'Đang thu thập tin tức báo chí...');
      return;
    }

    if (searchMode === 'ai') {
      setIsLoading(true);
      setLoadingStep(1);
      setLoadingMessage('Searching dictionary...');
      let foundEntry = null;
      let isOffline = false;

      try {
        const data = await searchWord(query);
        if (data.results && data.results.length > 0) {
          foundEntry = data.results[0];
        } else {
          // Explicit null if not found locally
          foundEntry = null; 
        }
      } catch (error) {
        isOffline = true;
        setBackendOffline(true);
      }

      // Fallback to public API if not found locally, OR if backend is offline
      if (!foundEntry) {
        foundEntry = await fetchFromPublicAPI(query);
      }

      if (foundEntry) {
        setDictResult(foundEntry);
        setIsDemoHello(true);
      } else {
        setNotFoundQuery(query);
        setIsDemoHello(true);
      }
      setIsLoading(false);
      setLoadingStep(0);
      return;
    }
  };

  const handleEdit = async (editPrompt: string) => {
    if (imageHistory.length === 0) return;
    const currentImage = imageHistory[0];
    setIsLoading(true);
    setError(null);
    setLoadingStep(2);
    setLoadingMessage(`Processing Modification: "${editPrompt}"...`);

    try {
      const base64Data = await editInfographicImage(currentImage.data, editPrompt);
      const newImage: GeneratedImage = {
        id: Date.now().toString(),
        data: base64Data,
        prompt: editPrompt,
        timestamp: Date.now(),
        searchMode: currentImage.searchMode
      };
      setImageHistory([newImage, ...imageHistory]);
    } catch (err: any) {
      console.error(err);
      setError('Modification failed. Try a different command.');
    } finally {
      setIsLoading(false);
      setLoadingStep(0);
    }
  };

  const restoreImage = (img: GeneratedImage) => {
     const newHistory = imageHistory.filter(i => i.id !== img.id);
     setImageHistory([img, ...newHistory]);
  };

  return (
    <>
    {showIntro ? (
      <IntroScreen onComplete={() => setShowIntro(false)} />
    ) : (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-200 font-sans selection:bg-cyan-500 selection:text-white pb-20 relative overflow-x-hidden animate-in fade-in duration-1000 transition-colors">
      
      {/* Background Elements */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-100 via-slate-50 to-white dark:from-indigo-900 dark:via-slate-950 dark:to-black z-0 transition-colors"></div>
      <div className="fixed inset-0 opacity-5 dark:opacity-20 z-0 pointer-events-none" style={{
          backgroundImage: `radial-gradient(currentColor 1px, transparent 1px)`,
          backgroundSize: '40px 40px'
      }}></div>

      {/* Navbar */}
      <header className="border-b border-slate-200 dark:border-white/10 sticky top-0 z-50 backdrop-blur-md bg-white/70 dark:bg-slate-950/60 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 md:h-20 flex items-center justify-between">
          <div className="flex items-center gap-3 md:gap-4 group">
            <div className="relative scale-90 md:scale-100">
                <div className="absolute inset-0 bg-cyan-500 blur-lg opacity-20 dark:opacity-40 group-hover:opacity-60 transition-opacity"></div>
                <div className="bg-white dark:bg-gradient-to-br dark:from-slate-900 dark:to-slate-800 p-2.5 rounded-xl border border-slate-200 dark:border-white/10 relative z-10 shadow-sm dark:shadow-none">
                   <Atom className="w-6 h-6 text-cyan-600 dark:text-cyan-400 animate-[spin_10s_linear_infinite]" />
                </div>
            </div>
            <div className="flex flex-col">
                <span className="font-display font-bold text-lg md:text-2xl tracking-tight text-slate-900 dark:text-white leading-none">
                Adam <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-600 to-indigo-600 dark:from-cyan-400 dark:to-amber-400">Dictionary</span>
                </span>
                <span className="text-[8px] md:text-[10px] uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400 font-medium">Knowledge Search Engine</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
              <button 
                className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-cyan-600 to-indigo-600 dark:from-cyan-500 dark:to-blue-500 text-white text-sm font-bold shadow-sm hover:shadow-md transition-all hover:brightness-110"
              >
                <Download className="w-4 h-4" />
                <span>Download App</span>
              </button>
              <button 
                onClick={() => setIsDarkMode(!isDarkMode)}
                className="p-2 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-cyan-600 dark:hover:text-cyan-300 transition-colors border border-slate-200 dark:border-white/10 shadow-sm"
                title={isDarkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
              >
                {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
          </div>
        </div>
      </header>

      <main className="px-3 sm:px-6 py-4 md:py-8 relative z-10">
        
        <div className={`max-w-6xl mx-auto transition-all duration-500 ${(imageHistory.length > 0 || isDemoHello) ? 'mb-4 md:mb-8' : 'min-h-[50vh] md:min-h-[70vh] flex flex-col justify-center'}`}>
          
          {(!imageHistory.length && !isDemoHello) && (
            <div className="text-center mb-6 md:mb-16 space-y-3 md:space-y-8 animate-in slide-in-from-bottom-8 duration-700 fade-in">
              <div className="inline-flex items-center justify-center gap-2 px-4 py-1.5 rounded-full bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 text-amber-600 dark:text-amber-300 text-[10px] md:text-xs font-bold tracking-widest uppercase shadow-sm dark:shadow-[0_0_20px_rgba(251,191,36,0.1)] backdrop-blur-sm">
                <Compass className="w-3 h-3 md:w-4 md:h-4" /> Explore and learn new words through Google and Games.
              </div>
              <h1 className="text-3xl sm:text-5xl md:text-8xl font-display font-bold text-slate-900 dark:text-white tracking-tight leading-[0.95] md:leading-[0.9]">
                Search <br/>
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-600 via-indigo-600 to-purple-600 dark:from-cyan-400 dark:via-indigo-400 dark:to-purple-400">The Unknown.</span>
              </h1>
              <p className="text-sm md:text-2xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto font-light leading-relaxed px-4">
                Search for definitions and knowledge powered by Google search grounding.
              </p>
            </div>
          )}

          {/* Search Form */}
          <form onSubmit={handleGenerate} className={`relative z-20 transition-all duration-300 ${isLoading ? 'opacity-50 pointer-events-none scale-95 blur-sm' : 'scale-100'}`}>
            
            <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 via-purple-500 to-amber-500 rounded-3xl opacity-10 dark:opacity-20 group-hover:opacity-30 dark:group-hover:opacity-40 transition duration-500 blur-xl"></div>
                
                <div className="relative bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border border-slate-200 dark:border-white/10 p-2 rounded-3xl shadow-2xl">
                    
                    {/* Main Input */}
                    <div className="relative flex items-center pr-2 md:pr-3">
                        <Search className="absolute left-4 md:left-6 w-5 h-5 md:w-6 md:h-6 text-slate-400 group-focus-within:text-cyan-500 transition-colors pointer-events-none z-10" />
                        
                        {ghostText && ghostText.toLowerCase().startsWith(topic.toLowerCase()) && (
                           <div className="absolute left-12 md:left-16 right-4 py-3 md:py-6 text-base md:text-2xl font-medium text-slate-400/50 pointer-events-none z-0 flex items-center">
                               <span className="opacity-0">{topic}</span>
                               <span>{ghostText.slice(topic.length)}</span>
                           </div>
                        )}

                        <input
                            type="text"
                            value={topic}
                            onChange={handleInputChange}
                            placeholder={ghostText ? "" : "What do you want to search?"}
                            className="flex-1 w-full pl-12 md:pl-16 pr-4 py-3 md:py-6 bg-transparent border-none outline-none text-base md:text-2xl placeholder:text-slate-400 font-medium text-slate-900 dark:text-white z-10 relative"
                        />
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="flex-shrink-0 bg-gradient-to-r from-cyan-600 to-blue-600 text-white px-5 md:px-8 py-2.5 md:py-4 rounded-xl md:rounded-2xl font-bold font-display tracking-wide hover:brightness-110 transition-all shadow-[0_0_20px_rgba(6,182,212,0.3)] whitespace-nowrap flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
                        >
                            <Microscope className="w-4 h-4 md:w-5 md:h-5" />
                            <span className="text-sm md:text-base">SEARCH</span>
                        </button>
                    </div>

                    {/* Controls Bar */}
                    <div className="flex flex-col md:flex-row gap-2 p-2 mt-2">
                    
                    {/* Level Selector */}
                    <button 
                        type="button"
                        onClick={() => handleModeSwitch('news')}
                        className={`flex-1 rounded-2xl border px-4 py-3 flex items-center justify-center gap-3 transition-colors ${searchMode === 'news' ? 'bg-cyan-500/10 border-cyan-500/50 text-cyan-600 dark:text-cyan-400' : 'bg-slate-50 dark:bg-slate-950/50 border-slate-200 dark:border-white/5 text-slate-500 hover:border-cyan-500/30'}`}
                    >
                        <Newspaper className="w-4 h-4" />
                        <span className="text-[10px] md:text-xs font-bold uppercase tracking-wider">Tìm kiếm qua báo</span>
                    </button>

                    {/* Style Selector */}
                    <button 
                        type="button"
                        onClick={() => handleModeSwitch('video')}
                        className={`flex-1 rounded-2xl border px-4 py-3 flex items-center justify-center gap-3 transition-colors ${searchMode === 'video' ? 'bg-purple-500/10 border-purple-500/50 text-purple-600 dark:text-purple-400' : 'bg-slate-50 dark:bg-slate-950/50 border-slate-200 dark:border-white/5 text-slate-500 hover:border-purple-500/30'}`}
                    >
                        <Youtube className="w-4 h-4" />
                        <span className="text-[10px] md:text-xs font-bold uppercase tracking-wider">Tìm kiếm qua Video youtube</span>
                    </button>

                     {/* Language Selector */}
                     <button 
                        type="button"
                        onClick={() => handleModeSwitch('ai')}
                        className={`flex-1 rounded-2xl border px-4 py-3 flex items-center justify-center gap-3 transition-colors ${searchMode === 'ai' ? 'bg-green-500/10 border-green-500/50 text-green-600 dark:text-green-400' : 'bg-slate-50 dark:bg-slate-950/50 border-slate-200 dark:border-white/5 text-slate-500 hover:border-green-500/30'}`}
                    >
                        <Globe className="w-4 h-4" />
                        <span className="text-[10px] md:text-xs font-bold uppercase tracking-wider">Tìm kiếm với AI</span>
                    </button>



                    </div>
                </div>
            </div>
          </form>
        </div>

        {isLoading && <Loading status={loadingMessage} step={loadingStep} facts={loadingFacts} searchMode={searchMode} />}

        {error && (
          <div className="max-w-2xl mx-auto mt-8 p-6 bg-red-100 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-2xl flex items-center gap-4 text-red-800 dark:text-red-200 backdrop-blur-sm animate-in fade-in slide-in-from-bottom-4 shadow-sm">
            <AlertCircle className="w-6 h-6 flex-shrink-0 text-red-500 dark:text-red-400" />
            <div className="flex-1">
                <p className="font-medium">{error}</p>
            </div>
          </div>
        )}

        {backendOffline && (
          <div className="max-w-2xl mx-auto mt-4 p-4 bg-amber-100 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-xl text-amber-800 dark:text-amber-200 text-center text-sm font-medium animate-in fade-in slide-in-from-bottom-4 shadow-sm backdrop-blur-sm">
            Backend đang offline. Chạy: <code className="bg-amber-200/50 dark:bg-amber-500/20 px-2 py-0.5 rounded font-mono">python backend.py</code>
          </div>
        )}

        {isDemoHello && <DemoHelloResults 
          searchMode={searchMode} 
          entry={dictResult} 
          notFoundQuery={notFoundQuery} 
          videos={videos}
          videoError={videoError}
          articles={newsArticles}
          topic={topic}
        />}

        {imageHistory.length > 0 && !isLoading && (
            <>
                <Infographic 
                    image={imageHistory[0]} 
                    onEdit={handleEdit} 
                    isEditing={isLoading}
                />
                <SearchResults results={currentSearchResults} />
            </>
        )}

        {imageHistory.length > 1 && (
            <div className="max-w-7xl mx-auto mt-16 md:mt-24 border-t border-slate-200 dark:border-white/10 pt-12 transition-colors">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-[0.2em] mb-8 flex items-center gap-3">
                    <History className="w-4 h-4" />
                    Session Archives
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 md:gap-6">
                    {imageHistory.slice(1).map((img) => (
                        <div 
                            key={img.id} 
                            onClick={() => restoreImage(img)}
                            className="group relative cursor-pointer rounded-2xl overflow-hidden border border-slate-200 dark:border-white/10 hover:border-cyan-500/50 transition-all shadow-lg bg-white dark:bg-slate-900/50 backdrop-blur-sm"
                        >
                            <img src={img.data} alt={img.prompt} className="w-full aspect-video object-cover opacity-90 dark:opacity-70 group-hover:opacity-100 transition-opacity duration-500" />
                            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-4 pt-8 translate-y-4 group-hover:translate-y-0 transition-transform duration-300">
                                <p className="text-xs text-white font-bold truncate mb-1 font-display">{img.prompt}</p>
                                <div className="flex gap-2">
                                    {img.level && <span className="text-[9px] text-cyan-100 uppercase font-bold tracking-wide px-1.5 py-0.5 rounded-full bg-cyan-900/60 border border-cyan-500/20">{img.level}</span>}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        )}

      </main>
    </div>
    )}
    </>
  );
};

export default App;