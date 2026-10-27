import { Bookmark, Shuffle, Sparkles } from 'lucide-react';
import AccountButton from './AccountButton';
import GradientASCII from './GradientASCII';
import PromptBar from './PromptBar';
import SplitText from './SplitText';
import { useT } from '../i18n';
import { mediaKey } from '../lib/media';
import './SearchStage.css';

const CHIP_LIMIT = 6;

export default function SearchStage({
  suggestions = [],
  busy = false,
  savedCount = 0,
  canShuffle = false,
  onSubmit,
  onStop,
  onOpen,
  onList,
  onBrowse,
  onShuffle,
  dubLang,
  onDubLangChange
}) {
  const t = useT();
  const chips = suggestions.slice(0, CHIP_LIMIT);

  return (
    <main className="stage view">
      <div className="stage__sky" aria-hidden="true">
        <div className="stage__art">
          <GradientASCII
            shape="horizon"
            colors={['#0a2a8f', '#7cc4ff', '#dce8ff', '#0a1ea0']}
            gradientOpacity={0.62}
            glyphOpacity={0.42}
            glow={0.4}
            density={0.52}
            softness={0.62}
            speed={0.7}
            mouseInteraction={false}
            clickEffect="none"
          />
        </div>
        <div className="stage__stars" />
        <div className="stage__glow" />
      </div>

      <div className="stage__account">
        <AccountButton onList={onList} />
      </div>

      <div className="stage__inner">
        <span className="stage__badge">
          <Sparkles size={13} />
          {t('home.badge')}
        </span>

        <SplitText
          text={t('home.title')}
          tag="h1"
          className="stage__title"
          effect="rise"
          splitType="words"
          delay={42}
          duration={1}
          staggerFrom="start"
          trigger="load"
          mask
          textAlign="center"
        />
        <p className="stage__sub">{t('home.subtitle')}</p>

        <div className="stage__bar">
          <PromptBar
            placeholder={t('search.placeholder')}
            sources={[]}
            commands={[]}
            busy={busy}
            onSend={onSubmit}
            onStop={onStop}
            width={780}
            radius={20}
            maxRows={4}
            background="rgba(21, 66, 186, 0.55)"
            menuBackground="rgba(6, 22, 86, 0.96)"
            color="#eaf2ff"
            sparkColor="#8ab8ff"
            className="stage__prompt"
            lang={dubLang}
            onLangChange={onDubLangChange}
          />
        </div>

        {chips.length ? (
          <div className="stage__chips" aria-label={t('nav.surprise')}>
            {chips.map(item => (
              <button
                key={mediaKey(item)}
                type="button"
                className="stage__chip"
                onClick={() => onOpen?.(item)}
                title={item.title}
              >
                {item.poster ? <img src={item.poster} alt="" loading="lazy" /> : null}
                <span className="stage__chip-title">{item.title}</span>
                <small>
                  {item.kind === 'tv' ? t('home.series') : item.kind === 'anime' ? 'Anime' : t('home.movies')}
                </small>
              </button>
            ))}
          </div>
        ) : null}

        <div className="stage__quick">
          <button type="button" className="stage__quick-btn" onClick={onList}>
            <Bookmark size={14} />
            {t('home.list')}
            {savedCount ? <b>{savedCount}</b> : null}
          </button>
          <button type="button" className="stage__quick-btn" onClick={() => onBrowse?.('movie')}>
            {t('home.movies')}
          </button>
          <button type="button" className="stage__quick-btn" onClick={() => onBrowse?.('tv')}>
            {t('home.series')}
          </button>
          <button type="button" className="stage__quick-btn" onClick={onShuffle} disabled={!canShuffle}>
            <Shuffle size={14} />
            {t('home.shuffle')}
          </button>
        </div>
      </div>

      <p className="stage__foot">{t('home.foot')}</p>
    </main>
  );
}
