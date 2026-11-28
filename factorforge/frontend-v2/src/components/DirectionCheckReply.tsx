import React, { useState } from 'react';
import { AlertTriangle, BookOpen, CheckCircle2, ChevronDown, ChevronRight, Database, ExternalLink, HelpCircle, XCircle } from 'lucide-react';
import type { DataCategory, DirectionCheckResult, DirectionConcept, DirectionVerdict, ConceptStatus } from '@/services/api';

interface Props {
  result: DirectionCheckResult;
  zh: boolean;
  disabled?: boolean;
  onStart: (direction: string) => void;
  onUseSuggestion: (direction: string) => void;
}

const VERDICT_STYLE: Record<DirectionVerdict, { cls: string; icon: React.ElementType; zh: string; en: string }> = {
  feasible: { cls: 'border-emerald-200 bg-emerald-50 text-emerald-800', icon: CheckCircle2, zh: '可以用现有数据检验', en: 'Testable with the stored data' },
  partial: { cls: 'border-amber-200 bg-amber-50 text-amber-800', icon: AlertTriangle, zh: '部分数据缺失', en: 'Some required data is missing' },
  unavailable: { cls: 'border-rose-200 bg-rose-50 text-rose-800', icon: XCircle, zh: '缺少所需数据，无法检验', en: 'Not testable: required data is missing' },
  unclear: { cls: 'border-slate-200 bg-slate-50 text-slate-700', icon: HelpCircle, zh: '未能判断数据需求', en: 'Data needs could not be determined' },
  no_data: { cls: 'border-rose-200 bg-rose-50 text-rose-800', icon: XCircle, zh: '数据库未构建', en: 'No data store built' },
};

const STATUS_STYLE: Record<ConceptStatus, { cls: string; zh: string; en: string }> = {
  available: { cls: 'bg-emerald-100 text-emerald-800', zh: '有数据', en: 'available' },
  proxy: { cls: 'bg-amber-100 text-amber-800', zh: '仅有替代', en: 'proxy only' },
  missing: { cls: 'bg-rose-100 text-rose-800', zh: '缺失', en: 'missing' },
  wrong_market: { cls: 'bg-slate-200 text-slate-700', zh: '不属于此市场', en: 'other market' },
};

const ExtLink: React.FC<{ href: string; children: React.ReactNode }> = ({ href, children }) => (
  <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-start gap-1 text-emerald-700 hover:underline">
    <span>{children}</span>
    <ExternalLink className="mt-0.5 h-3 w-3 shrink-0" />
  </a>
);

const CategoryBlock: React.FC<{ category: DataCategory; zh: boolean }> = ({ category, zh }) => (
  <div className="mt-2 rounded-lg border border-slate-200 bg-white/70 p-3">
    <div className="text-xs font-semibold text-slate-700">{zh ? category.labelZh : category.label}</div>
    {!category.appliesToMarket && (
      <div className="mt-1 text-xs text-slate-500">
        {zh ? '这类数据属于其他市场；如需研究请在设置中切换市场。' : 'This data belongs to another market; switch the market in Settings to study it.'}
      </div>
    )}
    {category.note && <div className="mt-1 text-xs text-slate-500">{category.note}</div>}
    {category.sources.length > 0 && (
      <div className="mt-2">
        <div className="mb-1 flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          <Database className="h-3 w-3" /> {zh ? '数据来源' : 'Where to get it'}
        </div>
        <ul className="space-y-1 text-xs">
          {category.sources.map((source) => (
            <li key={source.url + source.name}>
              <ExtLink href={source.url}>{source.name}</ExtLink>
              {source.kind && <span className="ml-1.5 rounded bg-slate-100 px-1 py-0.5 font-mono text-[10px] text-slate-500">{source.kind}</span>}
              {source.access && <span className="ml-1.5 text-slate-500">· {source.access}</span>}
            </li>
          ))}
        </ul>
      </div>
    )}
    {category.papers.length > 0 && (
      <div className="mt-2">
        <div className="mb-1 flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          <BookOpen className="h-3 w-3" /> {zh ? '代表性文献' : 'Papers that use it'}
        </div>
        <ul className="space-y-1 text-xs">
          {category.papers.map((paper) => (
            <li key={paper.url}><ExtLink href={paper.url}>{paper.citation}</ExtLink></li>
          ))}
        </ul>
      </div>
    )}
  </div>
);

const ConceptRow: React.FC<{ concept: DirectionConcept; zh: boolean }> = ({ concept, zh }) => {
  const style = STATUS_STYLE[concept.status] ?? STATUS_STYLE.missing;
  const missing = concept.status === 'missing' || concept.status === 'wrong_market';
  return (
    <li className="py-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${style.cls}`}>{zh ? style.zh : style.en}</span>
        <span className="font-medium text-slate-800">{concept.concept}</span>
        {concept.fields.map((field) => (
          <code key={field} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">${field}</code>
        ))}
      </div>
      {concept.note && <div className="mt-1 text-xs text-slate-500">{concept.note}</div>}
      {concept.inventedFields.length > 0 && (
        <div className="mt-1 text-xs text-rose-700">
          {zh ? '模型提到但数据库中不存在的字段：' : 'Fields the model named that do not exist: '}
          {concept.inventedFields.map((f) => `$${f}`).join(', ')}
        </div>
      )}
      {missing && concept.categories.map((category) => (
        <CategoryBlock key={category.id} category={category} zh={zh} />
      ))}
      {missing && concept.searchLinks.length > 0 && (
        <div className="mt-2 text-xs text-slate-600">
          {zh ? '暂无经核实的数据源条目，可以从这些搜索入手：' : 'No checked source on file yet. Start from these searches: '}
          {concept.searchLinks.map((link, i) => (
            <span key={link.url}>{i > 0 && ' · '}<ExtLink href={link.url}>{link.name}</ExtLink></span>
          ))}
          <span className="ml-1 text-slate-400">({concept.searchTerms.join(', ')})</span>
        </div>
      )}
    </li>
  );
};

export const DirectionCheckReply: React.FC<Props> = ({ result, zh, disabled = false, onStart, onUseSuggestion }) => {
  const [showReplication, setShowReplication] = useState(false);
  const [showFields, setShowFields] = useState(false);
  const verdict = VERDICT_STYLE[result.verdict] ?? VERDICT_STYLE.unclear;
  const VerdictIcon = verdict.icon;
  const canStart = Boolean(result.runDirection) && result.verdict !== 'unavailable' && result.verdict !== 'no_data';

  return (
    <div className="space-y-3">
      <div className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold ${verdict.cls}`}>
        <VerdictIcon className="h-3.5 w-3.5" /> {zh ? verdict.zh : verdict.en}
      </div>
      <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{result.reply}</p>

      {result.concepts.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {result.concepts.map((concept, i) => <ConceptRow key={i} concept={concept} zh={zh} />)}
        </ul>
      )}

      {result.replication && result.replication.sources.length > 0 && (
        <div>
          <button type="button" onClick={() => setShowReplication((v) => !v)} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-slate-900">
            {showReplication ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            {zh ? '已发表因子的开源复现库' : 'Open replications of published signals'}
          </button>
          {showReplication && (
            <ul className="mt-1 space-y-1 pl-5 text-xs">
              {result.replication.sources.map((s) => <li key={s.url}><ExtLink href={s.url}>{s.name}</ExtLink></li>)}
              {result.replication.papers.map((p) => <li key={p.url}><ExtLink href={p.url}>{p.citation}</ExtLink></li>)}
            </ul>
          )}
        </div>
      )}

      <div className="text-xs text-slate-500">
        <button type="button" onClick={() => setShowFields((v) => !v)} className="inline-flex items-center gap-1 hover:text-slate-800">
          {showFields ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          {zh ? `数据库中的 ${result.storeFieldCount} 个字段` : `${result.storeFieldCount} fields in the database`}
          {result.storePath ? <span className="ml-1 font-mono text-[11px] text-slate-400">{result.storePath}</span> : null}
        </button>
        {showFields && (
          <div className="mt-1 flex flex-wrap gap-1 pl-5">
            {result.storeFields.map((f) => <code key={f} className="rounded bg-slate-100 px-1 py-0.5 text-[11px]">${f}</code>)}
          </div>
        )}
      </div>

      {result.llm.error && (
        <div className="text-xs text-amber-700">
          {zh ? '模型检查未完成，以上结果仅来自关键词扫描：' : 'The model check did not complete; this answer comes from a keyword scan only: '}
          <span className="font-mono">{result.llm.error}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        {canStart && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => onStart(result.runDirection as string)}
            className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {result.verdict === 'feasible'
              ? (zh ? '开始挖掘' : 'Start mining')
              : (zh ? '仅用现有数据开始挖掘' : 'Start with the available data only')}
          </button>
        )}
        {result.suggestedDirection && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => onUseSuggestion(result.suggestedDirection as string)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {zh ? '改用建议的方向' : 'Use the suggested direction'}
          </button>
        )}
      </div>
      {result.suggestedDirection && (
        <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <span className="font-semibold">{zh ? '建议方向：' : 'Suggested: '}</span>{result.suggestedDirection}
        </div>
      )}
    </div>
  );
};
