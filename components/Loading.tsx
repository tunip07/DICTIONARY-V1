/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/
import React, { useEffect, useState } from 'react';
import { Loader2, BrainCircuit, BookOpen, Lightbulb, ScrollText, Database, Dna, Microscope, Globe, Compass, Newspaper, Youtube, PlayCircle, Radio, Rss, Film, Video } from 'lucide-react';
import { SearchMode } from '../types';

interface LoadingProps {
  status: string;
  step: number;
  facts?: string[];
  searchMode?: SearchMode;
  bare?: boolean;
}

const Loading: React.FC<LoadingProps> = ({ status, step, facts = [], searchMode = 'ai', bare = false }) => {
  const [currentFactIndex, setCurrentFactIndex] = useState(0);
  
  if (searchMode === 'ai') {
    return (
      <div className="w-full max-w-2xl mx-auto flex flex-col items-center justify-center py-16 px-4 animate-in fade-in duration-500">
        <div className="relative w-20 h-20 mb-8">
            <div className="absolute inset-0 border-4 border-slate-800 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-cyan-500 rounded-full border-t-transparent animate-spin"></div>
            <div className="absolute inset-0 flex items-center justify-center">
                <BrainCircuit className="w-8 h-8 text-cyan-400 animate-pulse" />
            </div>
        </div>
        <h3 className="text-cyan-400 font-display tracking-widest uppercase text-sm mb-2 animate-pulse">
            {status || "Đang phân tích..."}
        </h3>
        <p className="text-slate-500 text-xs italic">
            Vui lòng đợi trong giây lát
        </p>
      </div>
    );
  }

  useEffect(() => {
    if (facts.length > 0) {
      const interval = setInterval(() => {
        setCurrentFactIndex((prev) => (prev + 1) % facts.length);
      }, 3500);
      return () => clearInterval(interval);
    }
  }, [facts]);

  // A mix of Icons and Text flying into the center
  const FlyingItem = ({ delay, position, type, content }: { delay: number, position: number, type: 'icon' | 'text', content: any }) => {
    const startLeft = position % 2 === 0 ? '-20%' : '120%';
    const startTop = `${(position * 7) % 100}%`;
    
    return (
      <div 
        className={`absolute flex items-center justify-center font-bold opacity-0 select-none ${type === 'text' ? 'text-cyan-600 dark:text-cyan-400 text-[10px] md:text-xs tracking-[0.2em] bg-white/80 dark:bg-slate-900/80 border border-cyan-500/30 px-2 py-0.5 md:px-3 md:py-1 rounded shadow-[0_0_10px_rgba(6,182,212,0.3)] backdrop-blur-sm' : 'text-amber-500 dark:text-amber-400'}`}
        style={{
          animation: `implode 2.5s infinite ease-in ${delay}s`,
          top: startTop,
          left: startLeft,
          zIndex: 10,
        }}
      >
        {type === 'icon' ? React.createElement(content, { className: "w-5 h-5 md:w-6 md:h-6 filter drop-shadow-[0_0_8px_rgba(251,191,36,0.5)]" }) : content}
      </div>
    );
  };

  return (
    <div className={bare ? "relative flex flex-col items-center justify-center w-full min-h-[300px]" : "relative flex flex-col items-center justify-center w-full max-w-4xl mx-auto mt-8 min-h-[350px] md:min-h-[500px] overflow-hidden rounded-3xl bg-white/40 dark:bg-slate-900/40 border border-slate-200 dark:border-white/10 shadow-2xl backdrop-blur-md transition-colors"}>
      
      <style>{`
        @keyframes implode {
          0% { transform: scale(1) rotate(0deg); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: scale(0.1) rotate(360deg); opacity: 0; top: 40%; left: 50%; }
        }
        @keyframes spin-slow {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes spin-reverse {
          0% { transform: rotate(360deg); }
          100% { transform: rotate(0deg); }
        }
        @keyframes pulse-core {
          0% { box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.7); transform: scale(1); }
          70% { box-shadow: 0 0 0 30px rgba(6, 182, 212, 0); transform: scale(1.05); }
          100% { box-shadow: 0 0 0 0 rgba(6, 182, 212, 0); transform: scale(1); }
        }
      `}</style>

      {/* THE REACTOR CORE */}
      <div className="relative z-20 mb-10 md:mb-16 scale-[0.65] md:scale-125 mt-4 md:mt-10">
        {/* Outer Rings */}
        <div className="absolute inset-0 w-64 h-64 -translate-x-[4.5rem] -translate-y-[4.5rem] border border-dashed border-cyan-700/30 dark:border-cyan-900/50 rounded-full animate-[spin-slow_20s_linear_infinite]"></div>
        <div className="absolute inset-0 w-48 h-48 -translate-x-12 -translate-y-12 border-2 border-dashed border-cyan-500/20 rounded-full animate-[spin-slow_10s_linear_infinite]"></div>
        <div className="absolute inset-0 w-40 h-40 -translate-x-8 -translate-y-8 border border-indigo-500/30 rounded-full animate-[spin-reverse_8s_linear_infinite]"></div>
        
        {/* Glowing Center */}
        <div className="relative bg-white/50 dark:bg-white/10 p-1 rounded-full shadow-[0_0_60px_rgba(6,182,212,0.4)] animate-[pulse-core_2s_infinite]">
           <div className="bg-[#0f172a] p-4 rounded-full flex items-center justify-center w-24 h-24 relative overflow-hidden border border-cyan-500/50">
              <div className="absolute inset-0 bg-gradient-to-br from-cyan-500 to-blue-600 opacity-10 dark:opacity-30"></div>
              {searchMode === 'ai' && <BrainCircuit className="w-12 h-12 text-cyan-400 animate-pulse relative z-10" />}
              {searchMode === 'news' && <Newspaper className="w-12 h-12 text-cyan-400 animate-pulse relative z-10" />}
              {searchMode === 'video' && <Youtube className="w-12 h-12 text-cyan-400 animate-pulse relative z-10" />}
              {/* Inner beams */}
              <div className="absolute top-0 left-1/2 w-[1px] h-full bg-cyan-400/50 animate-[spin-slow_2s_linear_infinite]"></div>
              <div className="absolute top-1/2 left-0 h-[1px] w-full bg-cyan-400/50 animate-[spin-slow_2s_linear_infinite]"></div>
           </div>
        </div>

        {/* Flying Particles IN to the core */}
        <div className="absolute top-1/2 left-1/2 w-[300px] md:w-[500px] h-[300px] md:h-[500px] -translate-x-1/2 -translate-y-1/2 pointer-events-none">
           {searchMode === 'ai' && (
             <>
               <FlyingItem content={BookOpen} type="icon" delay={0} position={1} />
               <FlyingItem content="HISTORY" type="text" delay={0.2} position={2} />
               <FlyingItem content={Microscope} type="icon" delay={0.5} position={3} />
               <FlyingItem content="SCIENCE" type="text" delay={0.7} position={4} />
               <FlyingItem content={Dna} type="icon" delay={1.0} position={5} />
               <FlyingItem content="FACTS" type="text" delay={1.2} position={6} />
               <FlyingItem content={Globe} type="icon" delay={1.5} position={7} />
               <FlyingItem content="DATA" type="text" delay={1.7} position={8} />
               <FlyingItem content={Compass} type="icon" delay={2.0} position={9} />
               <FlyingItem content={ScrollText} type="icon" delay={2.2} position={10} />
             </>
           )}
           {searchMode === 'news' && (
             <>
               <FlyingItem content={Newspaper} type="icon" delay={0} position={1} />
               <FlyingItem content="LATEST" type="text" delay={0.2} position={2} />
               <FlyingItem content={Globe} type="icon" delay={0.5} position={3} />
               <FlyingItem content="WORLD" type="text" delay={0.7} position={4} />
               <FlyingItem content={Radio} type="icon" delay={1.0} position={5} />
               <FlyingItem content="BREAKING" type="text" delay={1.2} position={6} />
               <FlyingItem content={Rss} type="icon" delay={1.5} position={7} />
               <FlyingItem content="UPDATES" type="text" delay={1.7} position={8} />
               <FlyingItem content={ScrollText} type="icon" delay={2.0} position={9} />
               <FlyingItem content="HEADLINES" type="text" delay={2.2} position={10} />
             </>
           )}
           {searchMode === 'video' && (
             <>
               <FlyingItem content={Youtube} type="icon" delay={0} position={1} />
               <FlyingItem content="VIDEO" type="text" delay={0.2} position={2} />
               <FlyingItem content={PlayCircle} type="icon" delay={0.5} position={3} />
               <FlyingItem content="STREAM" type="text" delay={0.7} position={4} />
               <FlyingItem content={Film} type="icon" delay={1.0} position={5} />
               <FlyingItem content="MEDIA" type="text" delay={1.2} position={6} />
               <FlyingItem content={Video} type="icon" delay={1.5} position={7} />
               <FlyingItem content="WATCH" type="text" delay={1.7} position={8} />
               <FlyingItem content={Globe} type="icon" delay={2.0} position={9} />
               <FlyingItem content="CONTENT" type="text" delay={2.2} position={10} />
             </>
           )}
        </div>
      </div>

      {/* Fact Display */}
      <div className="relative z-30 w-full max-w-lg bg-[#0f172a] rounded-2xl p-6 md:p-8 shadow-2xl border border-slate-700/50 text-center flex flex-col items-center transition-all duration-500 min-h-[140px] md:min-h-[160px]">
        
        <div className="flex items-center gap-3 mb-4">
            {step === 1 && <Globe className="w-4 h-4 text-amber-500 dark:text-amber-400 animate-spin" />}
            {step === 2 && <BookOpen className="w-4 h-4 text-cyan-600 dark:text-cyan-400 animate-spin" />}
            {step >= 3 && <Microscope className="w-4 h-4 text-emerald-500 dark:text-emerald-400 animate-bounce" />}
            <h3 className="text-cyan-400 font-bold text-[10px] md:text-xs tracking-[0.2em] uppercase font-display">
            {status}
            </h3>
        </div>

        <div className="flex-1 flex items-center justify-center px-4">
            {facts.length > 0 ? (
            <div key={currentFactIndex} className="animate-in slide-in-from-bottom-2 fade-in duration-500">
                <p className="text-base md:text-xl text-slate-300 font-serif-display leading-relaxed italic">
                "{facts[currentFactIndex]}"
                </p>
            </div>
            ) : (
            <div className="flex items-center gap-2 text-slate-500 italic font-light text-sm md:text-base">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Establishing connection...</span>
            </div>
            )}
        </div>
        
        {/* Progress Bar */}
        <div className="w-full h-1 bg-slate-800 mt-6 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-cyan-400 to-amber-400 transition-all duration-1000 ease-out relative overflow-hidden shadow-[0_0_10px_rgba(6,182,212,0.8)]"
              style={{ width: `${step * 20 + 10}%` }}
            >
                <div className="absolute inset-0 bg-white/50 animate-[shimmer_1s_infinite]"></div>
            </div>
        </div>
      </div>

      <style>{`
          @keyframes shimmer {
              0% { transform: translateX(-100%); }
              100% { transform: translateX(100%); }
          }
      `}</style>

    </div>
  );
};

export default Loading;