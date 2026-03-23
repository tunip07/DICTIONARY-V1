import React from 'react';
import { Volume2, Star, Pin, Clock, Play, Atom, Newspaper, Youtube } from 'lucide-react';
import Loading from './Loading';
import { SearchMode } from '../types';

interface DemoHelloResultsProps {
  searchMode: SearchMode;
  entry?: any;           
  notFoundQuery?: string;
  videos?: any[];
  videoError?: string;
  articles?: any[];
  topic?: string;
}

// placeholder logic removed

const DemoHelloResults: React.FC<DemoHelloResultsProps> = ({ searchMode, entry, notFoundQuery, videos = [], videoError = '', articles = [], topic }) => {
  const renderContent = () => {
    if (searchMode === 'ai') {
      if (notFoundQuery) {
        return (
          <div className="w-full max-w-3xl mx-auto animate-in fade-in slide-in-from-bottom-8 duration-1000">
            <div className="bg-[#1a2332] rounded-2xl border border-slate-700/50 overflow-hidden relative shadow-lg p-8 flex flex-col items-center gap-4 text-center">
              <h3 className="text-xl font-bold text-white">Không tìm thấy "{notFoundQuery}" trong từ điển</h3>
              <button 
                onClick={() => window.open(`https://www.google.com/search?q=${encodeURIComponent(notFoundQuery + ' meaning')}`, '_blank')}
                className="bg-cyan-600 text-white px-6 py-2 rounded-xl font-bold hover:bg-cyan-500 transition-colors"
              >
                Tìm trên Google →
              </button>
            </div>
          </div>
        );
      }

      if (entry) {
        return (
          <div className="w-full max-w-3xl mx-auto animate-in fade-in slide-in-from-bottom-8 duration-1000">
            <div className="bg-[#1a2332] rounded-2xl border border-slate-700/50 overflow-hidden relative shadow-lg">
              {/* Green left border accent */}
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#00d287]"></div>
              
              <div className="p-6 md:p-8 flex flex-col md:flex-row gap-6">
                {/* Left Column: Word info */}
                <div className="flex flex-col gap-4 min-w-[200px]">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-[#0f172a] border border-slate-700 flex items-center justify-center text-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.2)]">
                      <Atom className="w-7 h-7 animate-[spin_4s_linear_infinite]" />
                    </div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-3xl font-bold text-[#00d287]">{entry.word}</h2>
                      <Star className="w-5 h-5 text-slate-500" />
                    </div>
                  </div>
                  
                  <div className="relative pl-4 border-l-2 border-[#00d287] py-2">
                    <p className="text-slate-400 italic text-sm">
                      {entry.pos ? `[${entry.pos}] ` : ''}
                      {entry.ipauk ? `/${entry.ipauk}/` : ''}
                      {entry.level ? ` \u2022 CEFR ${entry.level}` : ''}
                    </p>
                  </div>
                </div>

                {/* Right Column: Definitions */}
                <div className="flex-1 flex flex-col gap-4">
                  <h3 className="text-xl font-bold text-white">
                    {entry.meaning}
                  </h3>
                  {entry.example && (
                    <p className="text-slate-400">
                      EN: {entry.example}
                    </p>
                  )}
                  
                  {entry.synonyms && entry.synonyms.length > 0 && (
                    <div className="mt-4 bg-[#0f172a] rounded-xl p-4 border border-slate-800">
                      <p className="text-sm">
                        <span className="text-amber-500">👉 Hay đi kèm với:</span>{' '}
                        <span className="text-amber-500/80 italic">{entry.synonyms.join(', ')}</span>
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      }
    }

    if (searchMode === 'news') {
      return (
        <div className="w-full max-w-4xl mx-auto flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-8 duration-1000">
          {articles && articles.length > 0 ? (
            <>
              <div className="flex items-center gap-3 mb-2 border-b border-slate-800 pb-4">
                <Newspaper className="w-6 h-6 text-cyan-400" />
                <h2 className="text-2xl font-bold text-white">Tin tức mới nhất về "{topic}"</h2>
              </div>
              {articles.map((article, idx) => (
                <div key={idx} onClick={() => window.open(article.link, '_blank')} className="group bg-[#1a2332] rounded-2xl border border-slate-700/50 overflow-hidden hover:border-cyan-500/50 transition-all cursor-pointer flex flex-col sm:flex-row">
                  <div className="sm:w-1/3 h-48 sm:h-auto bg-slate-800 relative overflow-hidden">
                    {article.image ? (
                      <img
                        src={article.image}
                        alt={article.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                          e.currentTarget.src = article.favicon;
                          e.currentTarget.style.padding = '20px';
                          e.currentTarget.style.objectFit = 'contain';
                          e.currentTarget.style.background = '#0f172a';
                        }}
                      />
                    ) : (
                      <img
                        src={article.favicon}
                        alt={article.source}
                        className="w-full h-full group-hover:scale-105 transition-transform duration-500"
                        style={{padding: '20px', objectFit: 'contain', background: '#0f172a'}}
                        referrerPolicy="no-referrer"
                      />
                    )}
                    {idx === 0 && <div className="absolute top-3 left-3 bg-cyan-500 text-white text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wider shadow-lg">Mới nhất</div>}
                  </div>
                  <div className="p-6 sm:w-2/3 flex flex-col justify-center">
                    <div className="flex items-center gap-3 text-xs text-slate-400 mb-3">
                      <span className="flex items-center gap-1 text-cyan-400"><Pin className="w-3 h-3" /> {article.source || "Google News"}</span>
                      {article.date && (
                        <>
                          <span>•</span>
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {article.date}</span>
                        </>
                      )}
                    </div>
                    <h3 className="text-xl font-bold text-white group-hover:text-cyan-400 transition-colors mb-3 line-clamp-2">
                      {article.title}
                    </h3>
                    <p className="text-slate-400 text-sm line-clamp-2">
                      {article.description}
                    </p>
                  </div>
                </div>
              ))}
            </>
          ) : (
            <Loading bare={true} status="Đang tải dữ liệu báo..." step={1} searchMode="news" />
          )}
        </div>
      );
    }

    if (searchMode === 'video') {
      return (
        <div className="w-full max-w-5xl mx-auto flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-8 duration-1000">
          {videos && videos.length > 0 ? (
            <>
              <div className="flex items-center gap-3 mb-2 border-b border-slate-800 pb-4">
                <Youtube className="w-6 h-6 text-red-500" />
                <h2 className="text-2xl font-bold text-white">Video liên quan đến "{topic}"</h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {videos.map((video, idx) => (
                    <div key={idx} onClick={() => window.open(video.url, '_blank')} className="group bg-[#1a2332] rounded-2xl border border-slate-700/50 overflow-hidden hover:border-red-500/50 transition-all cursor-pointer flex flex-col">
                      <div className="w-full aspect-video bg-slate-800 relative overflow-hidden">
                        <img src={video.thumbnail} alt="Video thumbnail" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 opacity-80 group-hover:opacity-100" referrerPolicy="no-referrer" />
                        <div className="absolute inset-0 flex items-center justify-center">
                          <div className="w-14 h-14 bg-red-600/90 rounded-full flex items-center justify-center shadow-lg transform group-hover:scale-110 transition-transform">
                            <Play className="w-6 h-6 text-white fill-white ml-1" />
                          </div>
                        </div>
                        {video.duration && (
                          <div className="absolute bottom-3 right-3 bg-black/80 text-white text-xs font-medium px-2 py-1 rounded">
                            {video.duration}
                          </div>
                        )}
                      </div>
                      <div className="p-5 flex gap-4">
                        <div className="w-10 h-10 rounded-full bg-slate-700 overflow-hidden flex-shrink-0 border border-slate-600">
                          <img src={`https://www.google.com/s2/favicons?domain=youtube.com&sz=64`} alt="Channel" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                        </div>
                        <div className="flex flex-col">
                          <h3 className="text-lg font-bold text-white group-hover:text-red-400 transition-colors line-clamp-2 leading-tight mb-1">
                            {video.title}
                          </h3>
                          <p className="text-slate-400 text-sm mb-1">{video.channel}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
            </>
          ) : videoError ? (
            <div className="py-8 text-center text-red-400 font-bold border border-red-500/30 rounded-2xl bg-red-500/10">
              {videoError === 'Invalid API key in config.json' || videoError === 'YouTube quota reached for today' ? (
                <div className="flex flex-col items-center gap-3 p-4">
                  <p className="text-lg">❌ {videoError}</p>
                  <p className="text-sm text-red-300 font-normal">Add your free YouTube API key to config.json to see related vocabulary videos here.</p>
                  <button onClick={() => window.open('https://console.cloud.google.com', '_blank')} className="mt-2 text-white bg-red-600 hover:bg-red-500 px-6 py-2 rounded-xl text-sm transition-colors shadow-lg">
                    Get Free API Key →
                  </button>
                </div>
              ) : (
                <p>❌ {videoError}</p>
              )}
            </div>
          ) : (
            <Loading bare={true} status="Đang tải dữ liệu video..." step={1} searchMode="video" />
          )}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="relative flex flex-col items-center justify-center w-full max-w-4xl mx-auto mt-8 min-h-[350px] md:min-h-[500px] overflow-hidden rounded-3xl bg-white/40 dark:bg-slate-900/40 border border-slate-200 dark:border-white/10 shadow-2xl backdrop-blur-md transition-colors p-6 md:p-8">
      {renderContent()}
    </div>
  );
};

export default DemoHelloResults;
