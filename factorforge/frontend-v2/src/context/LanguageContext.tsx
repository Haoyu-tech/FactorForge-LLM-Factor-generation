import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

export type AppLanguage = 'zh' | 'en';

interface LanguageContextValue {
  language: AppLanguage;
  setLanguage: (language: AppLanguage) => void;
  toggleLanguage: () => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

// Long phrases must precede short phrases because translation is substring-based.
const ENGLISH_PHRASES: Array<[string, string]> = [
  ['暂时无法连接研究服务，请检查服务是否已启动后重试。', 'Unable to connect to the research service. Check that it is running, then retry.'],
  ['研究服务暂时不可用，请稍后重试。', 'The research service is temporarily unavailable. Please try again shortly.'],
  ['当前挖掘任务结束后，后端将自动安全重载并启用模型选择；页面每30秒自动检测。', 'After the current mining task finishes, the backend will reload safely and enable model selection; this page checks every 30 seconds.'],
  ['股票池；Custom、Combined 和 WRDS Kelly 均可选择 LightGBM、PLS5 或 Lasso。', 'universe; Custom, Combined, and WRDS Kelly all support LightGBM, PLS5, or Lasso.'],
  ['股票池；自定义因子采用 TopK Dropout，WRDS Kelly 采用月度十分组组合并可选择 LightGBM、PLS5 或 Lasso。', 'universe; custom factors use TopK Dropout, while WRDS Kelly uses monthly decile portfolios with LightGBM, PLS5, or Lasso.'],
  ['WRDS：CRSP 动态 S&P 500 + Compustat + Fama–French', 'WRDS: CRSP Dynamic S&P 500 + Compustat + Fama–French'],
  ['挖掘方向（价量 + WRDS 基本面 + 资产定价）', 'Mining Directions (Price/Volume + WRDS Fundamentals + Asset Pricing)'],
  ['暴露诊断： gsector、ggroup、gind、gsubind 的覆盖率、平均/最大暴露及集中度', 'Exposure diagnostics: coverage, mean/maximum exposure, and concentration for gsector, ggroup, gind, and gsubind'],
  ['稳健性检验： ggroup 行业组内排名，并与主结果同时反馈给 LLM', 'Robustness check: rank within ggroup and send it to the LLM with the primary result'],
  ['默认主口径： gsector 板块内排名与行业中性化', 'Primary default: within-gsector ranking and industry neutralization'],
  ['标识口径：PERMNO；成分口径：按 MbrStartDt/MbrEndDt 动态替换', 'Identifier: PERMNO; membership changes dynamically using MbrStartDt/MbrEndDt'],
  ['复用本机 Claude Code 登录；默认使用 sonnet 控制成本。保存后重启后端生效。', 'Reuse the local Claude Code login; sonnet is the default for cost control. Restart the backend after saving.'],
  ['训练、验证、测试区间必须按顺序排列且不能重叠', 'Training, validation, and test periods must be ordered and non-overlapping'],
  ['训练、验证和测试区间', 'Training, Validation, and Test Periods'],
  ['构建/刷新动态 S&P 500 Qlib', 'Build/Refresh Dynamic S&P 500 Qlib'],
  ['检查 WRDS 数据', 'Check WRDS Data'],
  ['挖掘评价调仓频率', 'Mining Evaluation Rebalance Frequency'],
  ['挖掘阶段启用 LightGBM 组合训练', 'Enable LightGBM Combination Training During Mining'],
  ['单次回测最大执行时间 (秒)', 'Maximum Backtest Runtime (seconds)'],
  ['本地 Claude / Claude CLI（复用登录）', 'Local Claude / Claude CLI (reuse login)'],
  ['WRDS 生成的 Qlib 目录', 'WRDS-Generated Qlib Directory'],
  ['WRDS 根目录', 'WRDS Root Directory'],
  ['主数据源', 'Primary Data Source'],
  ['现有 Qlib 数据', 'Existing Qlib Data'],
  ['GICS 行业处理', 'GICS Industry Processing'],
  ['LLM 服务端点地址', 'LLM Service Endpoint'],
  ['Claude 模型', 'Claude Model'],
  ['日频', 'Daily'],
  ['周频', 'Weekly'],
  ['月频', 'Monthly'],
  ['标普500指数', 'S&P 500 Index'],
  ['标普500', 'S&P 500'],
  ['股票池', 'Universe'],
  ['因子源', 'Factor Source'],
  ['开始时间', 'Start Time'],
  ['训练耗时', 'Training Time'],
  ['总耗时', 'Total Time'],
  ['综合分', 'Composite Score'],
  ['覆盖率', 'Coverage'],
  ['来源', 'Source'],
  ['删除', 'Delete'],
  ['指标', 'Metric'],
  ['系数', 'Coefficient'],
  ['显著性', 'Significance'],
  ['样本数', 'Observations'],
  ['调仓', 'Rebalance'],
  ['预测目标：下一月超额收益 ret_exc_lead1m。缺失特征按当月横截面中位数填补；整月全缺失时使用中性值0。训练集拟合，验证集用于选择模型复杂度；收益、IC、十分组和 Long–Short 只在测试集统计。进入测试期后训练窗口持续扩张。', 'Target: next-month excess return (ret_exc_lead1m). Missing features are filled with the same-month cross-sectional median; a fully missing factor-month uses neutral value 0. The training set fits the model, the validation set selects complexity, and returns, IC, deciles, and Long–Short statistics are reported only on the test set. The training window expands through the test period.'],
  ['实际因子集合在每次重训时仅根据当时已有训练样本重新筛选，不使用未来月份的缺失情况。', 'At each refit, the factor set is selected only from the training history available at that time; future missingness is never used.'],
  ['每月取月末因子值，计算当月股票横截面相关系数，再对月份取平均。', 'Use month-end factor values, calculate the stock cross-sectional correlation each month, then average across months.'],
  ['综合质量评分：预测力、Long–Short收益与回撤、稳定性、FF Alpha显著性、换手和成本', 'Composite quality score: predictive power, Long–Short return and drawdown, stability, FF alpha significance, turnover, and cost'],
  ['换手为每次调仓时权重变化绝对值之和；Long–Short 使用50%多头和50%空头，总敞口100%。当前未计借券费和滑点。', 'Turnover is the sum of absolute weight changes at each rebalance. Long–Short uses 50% long and 50% short for 100% gross exposure. Borrowing fees and slippage are not currently included.'],
  ['三种方向都会计算并展示；该选项决定顶部摘要和主累计曲线。换手成本按成交名义金额的 5 bps 计入。', 'All three directions are calculated and shown; this choice controls the headline summary and main cumulative curve. Turnover cost is charged at 5 bps of traded notional.'],
  ['独立回测在', 'The independent backtest evaluates out-of-sample performance on the'],
  ['上评估因子的样本外表现。', '.'],
  ['使用股票池；自定义因子采用 TopK Dropout，WRDS Kelly 采用月度十分组组合并可选择 LightGBM、PLS5 或 Lasso。', 'The custom-factor mode uses TopK Dropout; WRDS Kelly uses monthly decile portfolios with LightGBM, PLS5, or Lasso.'],
  ['使用历史 S&P 500 成分股、月频数据和 Expanding Window。', 'uses historical S&P 500 constituents, monthly data, and an expanding window.'],
  ['全部历史模式删除时，会从所有历史因子库移除对应因子', 'In all-history mode, deletion removes the factor from every historical library'],
  ['该历史因子尚未保存独立解释。后续挖掘会把每个因子的经济逻辑、信号含义、统计证据、风险和结论分别写入因子库。', 'This historical factor has no saved standalone explanation. Future mining runs will save its economic rationale, signal interpretation, statistical evidence, risks, and conclusion.'],
  ['该历史因子尚未保存资产定价回归；重新运行单因子评价后会生成 FF3、FF3 + Mom、FF5 和 FF5 + Mom 结果。', 'This historical factor has no saved asset-pricing regression. Re-run single-factor evaluation to generate FF3, FF3 + Mom, FF5, and FF5 + Mom results.'],
  ['该旧因子没有保存分组曲线，请重新运行单因子评价后查看。', 'This legacy factor has no saved decile curve. Re-run single-factor evaluation to generate it.'],
  ['区间必须依次衔接且不能重叠；测试集同时作为 Long/Short 和资产定价检验区间。', 'Periods must be ordered and non-overlapping. The test set is also used for Long/Short and asset-pricing evaluation.'],
  ['每个选中频率都会计算 Long、Short、Long–Short、换手成本和十组单调性，并反馈给 LLM；至少保留一种。', 'Each selected frequency calculates Long, Short, Long–Short, turnover cost, and decile monotonicity for LLM feedback; keep at least one.'],
  ['未加前缀的 IC、Long/Short、十分组和 FF 回归均使用 gsector 行业中性信号。', 'Unprefixed IC, Long/Short, decile, and FF regression statistics use the gsector-neutral signal.'],
  ['默认关闭：逐个评价候选因子并建立因子库。开启后额外训练组合模型；独立模型回测不受影响。', 'Off by default: candidates are evaluated individually to build the factor library. When enabled, an additional combination model is trained; independent model backtests are unaffected.'],
  ['对应 Windows 的 D:/桌面文件/US stock research/wrds。原始文件保持在该目录，不复制 Kelly 153 压缩包。', 'Maps to D:/桌面文件/US stock research/wrds on Windows. Source files remain there; the Kelly 153 archive is not copied.'],
  ['历史 S&P 500 成分股、CRSP 行情及点时 Compustat 基本面', 'historical S&P 500 constituents, CRSP market data, and point-in-time Compustat fundamentals'],
  ['综合 IC、Long–Short、回撤、稳定性、FF Alpha、换手和成本', 'IC, Long–Short performance, drawdown, stability, FF alpha, turnover, and costs'],
  ['批量选择与删除', 'Bulk Selection and Deletion'],
  ['因子相关性热力图', 'Factor Correlation Heatmap'],
  ['未勾选时取当前排序前N个', 'If none are selected, use the top N in the current order'],
  ['正在读取真实因子值...', 'Reading actual factor values...'],
  ['至少需要两个有缓存的因子才能计算相关性。', 'At least two cached factors are required to calculate correlation.'],
  ['相关性计算失败', 'Correlation calculation failed'],
  ['个因子暂无可用信号缓存，未纳入矩阵。', ' factors have no usable signal cache and were excluded from the matrix.'],
  ['个可用因子', ' available factors'],
  ['已使用缓存结果', 'Cached result'],
  ['计算热力图', 'Calculate Heatmap'],
  ['计算已选', 'Calculate selected '],
  ['清空结果', 'Clear Results'],
  ['相关系数', 'Correlation'],
  ['Spearman（推荐）', 'Spearman (recommended)'],
  ['因子预测统计', 'Factor Predictive Statistics'],
  ['资产定价回归', 'Asset-Pricing Regressions'],
  ['行业中性与稳健性', 'Industry Neutrality and Robustness'],
  ['十组累计收益曲线', 'Decile Cumulative Return Curves'],
  ['Long / Short / Long–Short 回测', 'Long / Short / Long–Short Backtest'],
  ['LLM 因子解释', 'LLM Factor Explanation'],
  ['历史因子 · 本轮综合反馈', 'Historical Factor · Round Feedback'],
  ['完整原始指标', 'Complete Raw Metrics'],
  ['收益、回撤、换手和成本按组合腿并列展示', 'Returns, drawdown, turnover, and costs are shown by portfolio leg'],
  ['基于该因子的 Long–Short 净收益，使用 Newey–West 稳健标准误', 'Based on the factor Long–Short net return with Newey–West robust standard errors'],
  ['显著性：', 'Significance: '],
  ['样本数：', 'Observations: '],
  ['残差年化波动：', 'Annualized residual volatility: '],
  ['Newey–West 滞后：', 'Newey–West lags: '],
  ['平均绝对暴露', 'Mean Absolute Exposure'],
  ['最大绝对暴露', 'Maximum Absolute Exposure'],
  ['暴露 HHI', 'Exposure HHI'],
  ['GICS 层级', 'GICS Level'],
  ['十组检验', 'Decile Test'],
  ['分组数', 'Number of Groups'],
  ['经济逻辑', 'Economic Rationale'],
  ['信号含义', 'Signal Interpretation'],
  ['统计证据', 'Statistical Evidence'],
  ['风险与局限', 'Risks and Limitations'],
  ['结论与用法', 'Conclusion and Usage'],
  ['假设评价', 'Hypothesis Evaluation'],
  ['判断依据', 'Rationale'],
  ['本轮观察', 'Round Observations'],
  ['预测模型', 'Prediction Model'],
  ['训练样本缺失率上限', 'Training Missingness Limit'],
  ['模型样本缺失率', 'Model-Sample Missingness'],
  ['查看全部 153 个因子的 S&P 500 缺失率', 'View S&P 500 Missingness for All 153 Factors'],
  ['历史成分股月度样本', 'Historical constituent-month observations'],
  ['最早有效月', 'First Valid Month'],
  ['最近有效月', 'Last Valid Month'],
  ['有效观测', 'Valid Observations'],
  ['重新训练间隔', 'Refit Interval'],
  ['最短训练历史', 'Minimum Training History'],
  ['每12个月重训（默认）', 'Refit every 12 months (default)'],
  ['每6个月重训', 'Refit every 6 months'],
  ['每3个月重训', 'Refit every 3 months'],
  ['每月重训', 'Refit monthly'],
  ['非线性树模型，验证集选择迭代轮数', 'Nonlinear tree model; validation selects boosting rounds'],
  ['5个偏最小二乘潜变量', 'Five partial least-squares latent components'],
  ['最多5个偏最小二乘潜变量，验证集选择维数', 'Up to five PLS components; validation selects the dimension'],
  ['训练、验证和测试区间', 'Training, Validation, and Test Periods'],
  ['Kelly 使用月频 Expanding Window；进入测试期后训练窗口持续扩张。', 'Kelly uses a monthly expanding window; the training window continues to expand through the test period.'],
  ['Custom / Combined 使用训练集拟合、验证集选择模型复杂度，并只在测试集统计样本外结果。', 'Custom / Combined fit on the training set, select model complexity on validation, and report out-of-sample results only on the test set.'],
  ['稀疏线性模型，验证集选择惩罚强度', 'Sparse linear model; validation selects the penalty'],
  ['测试 / 回测集', 'Test / Backtest Set'],
  ['训练集', 'Training Set'],
  ['验证集', 'Validation Set'],
  ['组合方向', 'Portfolio Direction'],
  ['做多预测排名前10%', 'Long the top 10% by predicted score'],
  ['做空预测排名后10%', 'Short the bottom 10% by predicted score'],
  ['50%多头 + 50%空头', '50% long + 50% short'],
  ['Long / Short / Long–Short 明细（均已扣换手成本）', 'Long / Short / Long–Short Details (net of turnover costs)'],
  ['十分组累计净收益', 'Decile Cumulative Net Returns'],
  ['当前所选方向累计净收益曲线', 'Cumulative Net Return for Selected Direction'],
  ['年化毛收益', 'Annualized Gross Return'],
  ['年化净收益', 'Annualized Net Return'],
  ['年化扣费收益', 'Annualized Net Return'],
  ['累计交易成本', 'Cumulative Transaction Cost'],
  ['月均换手', 'Average Monthly Turnover'],
  ['日均换手', 'Average Daily Turnover'],
  ['因子源类型', 'Factor Source Type'],
  ['因子缓存状态', 'Factor Cache Status'],
  ['正在检查缓存状态...', 'Checking cache status...'],
  ['所有因子已缓存，回测将快速执行', 'All factors are cached; the backtest will run quickly'],
  ['未缓存（跳过）', 'Uncached (skipped)'],
  ['质量筛选在因子计算和训练前执行；每个档位单独保存回测结果。', 'Quality filtering runs before factor calculation and training; each tier saves separate backtest results.'],
  ['不按质量筛选', 'No quality filter'],
  ['综合分不足或关键指标为负', 'Low composite score or negative key metrics'],
  ['因子源：', 'Factor source: '],
  ['任务 ID：', 'Task ID: '],
  ['开始时间：', 'Start time: '],
  ['回测区间：', 'Backtest period: '],
  ['市场：', 'Market: '],
  ['基准：', 'Benchmark: '],
  ['运行日志', 'Run Logs'],
  ['条日志', ' log entries'],
  ['回测正在执行中', 'Backtest is running'],
  ['累计净收益：', 'Cumulative net return: '],
  ['全部历史因子（合并去重）', 'All Historical Factors (merged and deduplicated)'],
  ['综合分：高到低', 'Composite Score: High to Low'],
  ['综合分：低到高', 'Composite Score: Low to High'],
  ['挖掘时间：新到旧', 'Mining Time: Newest First'],
  ['删除所选', 'Delete Selected'],
  ['删除中...', 'Deleting...'],
  ['删除因子失败', 'Failed to delete factors'],
  ['当前因子库', 'current factor library'],
  ['全部历史因子库中的对应记录', 'matching records in all historical factor libraries'],
  ['收起', 'Collapse'],
  ['展开', 'Expand'],
  ['用自然语言描述需求，AI 自动挖掘高质量量化因子', 'Describe your research goal in natural language and let AI mine high-quality quantitative factors'],
  ['实验运行中...可以切换到其他页面，任务不会中断', 'Experiment running... you can switch pages without interrupting the task'],
  ['已开启自选挖掘方向，将使用「设置 → 挖掘方向」中的选项', 'Custom mining direction enabled; selections from Settings → Mining Directions will be used'],
  ['描述因子挖掘需求，或开启「自选挖掘方向」使用设置中的方向 (Shift+Enter 换行，Enter 发送)', 'Describe a factor-mining goal, or enable custom directions from Settings (Shift+Enter for newline, Enter to send)'],
  ['所有配置修改后会自动保存至后端环境文件及本地浏览器缓存。涉及 API 或路径的修改，建议在保存后重启相关服务以确保生效。', 'Changes are saved to the backend environment file and browser storage. Restart related services after changing API or path settings.'],
  ['使用因子库进行全周期回测评估', 'Run a full-period evaluation with a factor library'],
  ['回测仅使用已缓存的因子，未缓存因子将自动跳过。', 'The backtest uses cached factors only; uncached factors are skipped automatically.'],
  ['支持 OpenAI 兼容格式的 API Key（如 DashScope, DeepSeek 等）', 'Supports OpenAI-compatible API keys such as DashScope and DeepSeek'],
  ['复用 Windows Codex 已登录账号；修改后重启后端生效。', 'Reuse the signed-in Windows Codex account; restart the backend after changes.'],
  ['允许多个挖掘方向同时运行，显著加快实验速度，但会增加系统负载', 'Run multiple mining directions concurrently for faster experiments at higher system load'],
  ['自动检测并过滤低质量因子，防止其进入下一轮迭代，保证最终结果质量', 'Detect and filter low-quality factors before the next iteration'],
  ['选择作为默认参考的挖掘方向；启动任务时可从中选用或随机一条', 'Choose default reference directions; select or randomize one when starting a task'],
  ['使用下方选中的方向（启动时从选中中取一条或按业务逻辑使用）', 'Use one of the selected directions below when starting'],
  ['LLM 自动理解需求，生成因子假设并进化优化', 'The LLM interprets the goal, proposes factor hypotheses, and evolves them'],
  ['浏览、筛选、分析已挖掘的所有因子', 'Browse, filter, and analyze all mined factors'],
  ['选择因子库进行全周期样本外回测评估', 'Select a factor library for full-period out-of-sample evaluation'],
  ['后端服务未连接。请先启动后端：', 'Backend is not connected. Start it first: '],
  ['无法连接后端服务。请确保后端已启动 (python backend/app.py)', 'Cannot connect to the backend. Ensure it is running (python backend/app.py)'],
  ['无法从后端加载配置，显示的是本地缓存配置', 'Unable to load backend settings; showing locally cached settings'],
  ['确定要重置为默认配置吗？', 'Reset to default settings?'],
  ['当前无进行中的挖掘任务', 'No active mining task'],
  ['开始挖掘因子后，结果将显示在这里', 'Results will appear here after factor mining starts'],
  ['没有符合筛选条件的因子', 'No factors match the current filters'],
  ['用自然语言描述你想要挖掘的因子类型、策略思路或研究方向...', 'Describe the factor type, strategy idea, or research direction in natural language...'],
  ['搜索因子名称、表达式或描述...', 'Search factor names, expressions, or descriptions...'],
  ['单次实验同时探索的独立方向数量 (1-10)', 'Number of independent directions explored per experiment (1–10)'],
  ['因子自我进化和优化的最大迭代次数 (1-20)', 'Maximum factor evolution and optimization iterations (1–20)'],
  ['用于存放挖掘出的因子、回测报告及日志文件', 'Stores mined factors, backtest reports, and logs'],
  ['需包含 calendars/, features/, instruments/ 等 Qlib 标准数据子目录', 'Must contain Qlib directories such as calendars/, features/, and instruments/'],
  ['生成的因子将保存到此文件。支持字母、数字、下划线。', 'Generated factors are saved to this file. Letters, numbers, and underscores are supported.'],
  ['留空使用 Codex 当前默认模型', 'Leave blank to use the current Codex default model'],
  ['例如 momentum_v1 (留空则无后缀)', 'Example: momentum_v1 (blank means no suffix)'],
  ['正在解析用户需求...', 'Parsing the request...'],
  ['解析需求关键词...', 'Parsing request keywords...'],
  ['识别策略类型...', 'Identifying strategy type...'],
  ['生成研究方向...', 'Generating research directions...'],
  ['规划探索路径...', 'Planning exploration paths...'],
  ['初始化进化框架...', 'Initializing evolution framework...'],
  ['准备种子因子...', 'Preparing seed factors...'],
  ['生成因子假设...', 'Generating factor hypotheses...'],
  ['构建表达式...', 'Building expressions...'],
  ['计算因子值...', 'Calculating factor values...'],
  ['评估质量...', 'Evaluating quality...'],
  ['执行回测计算...', 'Running backtest...'],
  ['计算IC指标...', 'Calculating IC metrics...'],
  ['评估收益曲线...', 'Evaluating return curve...'],
  ['分析因子质量...', 'Analyzing factor quality...'],
  ['综合分析结果...', 'Synthesizing results...'],
  ['生成评估报告...', 'Generating evaluation report...'],
  ['优化因子组合...', 'Optimizing factor combination...'],
  ['任务完成!', 'Task completed!'],
  ['结果已生成!', 'Results generated!'],
  ['因子智研平台', 'Quant Research OS'],
  ['智能因子挖掘平台', 'Intelligent Factor Mining Platform'],
  ['欢迎使用 FactorForge', 'Welcome to FactorForge'],
  ['AI 因子挖掘', 'AI Factor Mining'],
  ['因子库管理', 'Factor Library Management'],
  ['使用须知', 'Usage Notes'],
  ['默认市场：', 'Default market: '],
  ['数据来源：', 'Data source: '],
  ['训练区间：', 'Training period: '],
  ['验证与测试：', 'Validation and test: '],
  ['挖掘方式：', 'Mining mode: '],
  ['质量标准：', 'Quality criteria: '],
  ['挖掘时间段：', 'Mining period: '],
  ['独立回测：', 'Independent backtest: '],
  ['资源消耗：', 'Resource usage: '],
  ['基础因子：', 'Base factors: '],
  ['因子挖掘', 'Factor Mining'],
  ['因子库', 'Factor Library'],
  ['独立回测', 'Independent Backtest'],
  ['回测配置', 'Backtest Configuration'],
  ['回测进度', 'Backtest Progress'],
  ['回测结果', 'Backtest Results'],
  ['回测指标', 'Backtest Metrics'],
  ['回测中', 'Backtesting'],
  ['回测', 'Backtest'],
  ['系统配置', 'System Settings'],
  ['管理 API 连接、数据源及实验参数', 'Manage API connections, data sources, and experiment parameters'],
  ['配置 API', 'API Configuration'],
  ['数据路径', 'Data Paths'],
  ['默认参数', 'Default Parameters'],
  ['挖掘方向', 'Mining Directions'],
  ['LLM 模型配置', 'LLM Model Configuration'],
  ['本地 GPT / Codex CLI（无需 API Key）', 'Local GPT / Codex CLI (no API key required)'],
  ['OpenAI 兼容 API', 'OpenAI-Compatible API'],
  ['Codex 模型（可留空）', 'Codex Model (optional)'],
  ['调用方式', 'Connection Method'],
  ['模型名称', 'Model Name'],
  ['后端连接状态：', 'Backend status: '],
  ['数据存储路径', 'Data Storage Paths'],
  ['Qlib 数据目录', 'Qlib Data Directory'],
  ['实验结果输出目录', 'Experiment Output Directory'],
  ['已识别的因子库', 'Detected Factor Libraries'],
  ['实验默认参数', 'Experiment Defaults'],
  ['并行方向数', 'Parallel Directions'],
  ['进化轮次', 'Evolution Rounds'],
  ['默认市场', 'Default Market'],
  ['回测超时 (秒)', 'Backtest Timeout (seconds)'],
  ['默认因子库名称后缀', 'Default Factor Library Suffix'],
  ['高级控制', 'Advanced Controls'],
  ['启用并行执行', 'Enable Parallel Execution'],
  ['启用质量门控', 'Enable Quality Gate'],
  ['参考方向（可多选）', 'Reference Directions (multiple selection)'],
  ['使用方式', 'Usage Mode'],
  ['配置提示', 'Configuration Tip'],
  ['保存配置', 'Save Settings'],
  ['配置已保存', 'Settings saved'],
  ['有未保存的更改', 'Unsaved changes'],
  ['加载配置中...', 'Loading settings...'],
  ['已连接', 'Connected'],
  ['未连接', 'Disconnected'],
  ['检测中...', 'Checking...'],
  ['因子库 JSON', 'Factor Library JSON'],
  ['因子源模式', 'Factor Source Mode'],
  ['同步缓存', 'Sync Cache'],
  ['预热缓存', 'Warm Cache'],
  ['开始回测', 'Start Backtest'],
  ['停止回测', 'Stop Backtest'],
  ['当前因子库 RankIC Top 10', 'Current Factor Library — RankIC Top 10'],
  ['因子总数量', 'Total Factors'],
  ['高质量因子数量', 'High-Quality Factors'],
  ['中等因子数量', 'Medium-Quality Factors'],
  ['低质量因子数量', 'Low-Quality Factors'],
  ['高质量', 'High Quality'],
  ['中等质量', 'Medium Quality'],
  ['低质量', 'Low Quality'],
  ['一键回测', 'Quick Backtest'],
  ['因子名', 'Factor Name'],
  ['因子名称', 'Factor Name'],
  ['因子描述', 'Factor Description'],
  ['因子表达式', 'Factor Expression'],
  ['数学公式', 'Formula'],
  ['表达式', 'Expression'],
  ['公式', 'Formula'],
  ['年化收益', 'Annualized Return'],
  ['夏普比率', 'Sharpe Ratio'],
  ['最大回撤', 'Maximum Drawdown'],
  ['卡玛比率', 'Calmar Ratio'],
  ['最终结果展示', 'Final Results'],
  ['等待任务完成...', 'Waiting for task completion...'],
  ['净值曲线', 'Equity Curve'],
  ['回撤分析', 'Drawdown Analysis'],
  ['因子质量分布', 'Factor Quality Distribution'],
  ['生成因子列表', 'Generated Factors'],
  ['执行进度', 'Execution Progress'],
  ['执行时间线', 'Execution Timeline'],
  ['实时日志', 'Live Logs'],
  ['等待日志输出...', 'Waiting for logs...'],
  ['解析需求', 'Parse Request'],
  ['规划方向', 'Plan Directions'],
  ['进化中', 'Evolving'],
  ['分析结果', 'Analyze Results'],
  ['暂无因子库文件', 'No factor library files'],
  ['最新因子库', 'Latest Factor Library'],
  ['暂无因子数据', 'No factor data'],
  ['暂无因子', 'No Factors'],
  ['浏览和管理挖掘的因子', 'Browse and manage mined factors'],
  ['总因子数', 'Total Factors'],
  ['创建时间:', 'Created:'],
  ['因子ID:', 'Factor ID:'],
  ['元信息', 'Metadata'],
  ['无描述', 'No description'],
  ['未知', 'Unknown'],
  ['返回主页', 'Back to Home'],
  ['返回', 'Back'],
  ['刷新', 'Refresh'],
  ['导出', 'Export'],
  ['重置', 'Reset'],
  ['设置', 'Settings'],
  ['全部', 'All'],
  ['核心', 'Core'],
  ['方向', 'Direction'],
  ['轮次', 'Round'],
  ['质量', 'Quality'],
  ['数量', 'Count'],
  ['完成', 'Completed'],
  ['失败', 'Failed'],
  ['运行中', 'Running'],
  ['已完成', 'Completed'],
  ['已缓存', 'Cached'],
  ['未缓存', 'Not Cached'],
  ['发送', 'Send'],
  ['中断实验', 'Stop Experiment'],
  ['高级配置', 'Advanced Configuration'],
  ['市场选择', 'Market'],
  ['开始执行', 'Start'],
  ['执行中...', 'Running...'],
  ['自选挖掘方向', 'Custom Mining Direction'],
  ['全选', 'Select All'],
  ['取消全选', 'Clear All'],
  ['随机', 'Random'],
  ['已选', 'Selected'],
  ['项', 'items'],
  ['最近', 'Latest'],
  ['条', 'entries'],
  ['正在', 'Processing'],
  ['完成', 'Done'],
  ['错误', 'Error'],
  ['警告', 'Warning'],
  ['成功', 'Success'],
  ['中等', 'Medium'],
  ['低质量', 'Low Quality'],
  ['高', 'High'],
  ['中', 'Medium'],
  ['低', 'Low'],
  ['沪深300', 'CSI 300'],
  ['中证500', 'CSI 500'],
  ['例如', 'e.g.'],
  ['秒', 'seconds'],
];

const SORTED_PHRASES = [...ENGLISH_PHRASES].sort((a, b) => b[0].length - a[0].length);

function translateStaticText(source: string): string {
  let output = source;
  for (const [zh, en] of SORTED_PHRASES) {
    // One- and two-character labels are common inside user text and generated
    // factor descriptions. Translate them only when they are standalone UI text.
    if ([...zh].length <= 2) {
      if (output.trim() === zh) {
        const leading = output.match(/^\s*/)?.[0] || '';
        const trailing = output.match(/\s*$/)?.[0] || '';
        output = `${leading}${en}${trailing}`;
      }
    } else {
      output = output.split(zh).join(en);
    }
  }
  output = output.replace(/第\s*(\d+)\s*轮/g, 'Round $1');
  output = output.replace(/第\s*(\d+)\s*组/g, 'Group $1');
  output = output.replace(/已选\s*(\d+)\s*个/g, '$1 selected');
  output = output.replace(/(\d+)\s*个可用因子/g, '$1 available factors');
  output = output.replace(/(\d+)\s*个月/g, '$1 months');
  output = output.replace(/(\d+)\s*个因子/g, '$1 factors');
  output = output.replace(/(\d+)\s*条日志/g, '$1 log entries');
  output = output.replace(/共\s*(\d+)\s*个因子/g, '$1 factors');
  output = output.replace(/已选\s*(\d+)\s*\/\s*(\d+)\s*项/g, '$1 / $2 selected');
  output = output.replace(/最近\s*(\d+)\s*条/g, 'Latest $1 entries');
  output = output.replace(/全部\s*\((\d+)\)/g, 'All ($1)');
  output = output.replace(/高质量\s*\((\d+)\)/g, 'High Quality ($1)');
  output = output.replace(/中等\s*\((\d+)\)/g, 'Medium ($1)');
  output = output.replace(/低质量\s*\((\d+)\)/g, 'Low Quality ($1)');
  return output;
}

const originalText = new WeakMap<Text, string>();
const translatedText = new WeakMap<Text, string>();
const originalAttrs = new WeakMap<Element, Map<string, string>>();
const translatedAttrs = new WeakMap<Element, Map<string, string>>();
const TRANSLATED_ATTRIBUTES = ['placeholder', 'title', 'aria-label'];

function translateNode(node: Node, language: AppLanguage) {
  if (node.nodeType === Node.TEXT_NODE) {
    const textNode = node as Text;
    const current = textNode.nodeValue || '';
    if (language === 'zh') {
      const source = originalText.get(textNode);
      if (source !== undefined && current === translatedText.get(textNode)) textNode.nodeValue = source;
      originalText.delete(textNode);
      translatedText.delete(textNode);
      return;
    }

    const last = translatedText.get(textNode);
    if (last !== undefined && current === last) return;
    // A React update may reuse a translated text node. Treat its new value as
    // fresh source text, then translate it again.
    const source = current;
    const target = translateStaticText(source);
    if (target === source) {
      originalText.delete(textNode);
      translatedText.delete(textNode);
      return;
    }
    originalText.set(textNode, source);
    translatedText.set(textNode, target);
    textNode.nodeValue = target;
    return;
  }

  if (!(node instanceof Element)) return;
  let originals = originalAttrs.get(node);
  let translated = translatedAttrs.get(node);
  if (!originals) {
    originals = new Map();
    originalAttrs.set(node, originals);
  }
  if (!translated) {
    translated = new Map();
    translatedAttrs.set(node, translated);
  }
  for (const attr of TRANSLATED_ATTRIBUTES) {
    if (!node.hasAttribute(attr)) continue;
    const current = node.getAttribute(attr) || '';
    if (language === 'zh') {
      const source = originals.get(attr);
      if (source !== undefined && current === translated.get(attr)) node.setAttribute(attr, source);
      originals.delete(attr);
      translated.delete(attr);
      continue;
    }
    const last = translated.get(attr);
    if (last !== undefined && current === last) continue;
    const source = current;
    const target = translateStaticText(source);
    if (target === source) {
      originals.delete(attr);
      translated.delete(attr);
      continue;
    }
    originals.set(attr, source);
    translated.set(attr, target);
    node.setAttribute(attr, target);
  }
  node.childNodes.forEach((child) => translateNode(child, language));
}

const AutoTranslator: React.FC<{ language: AppLanguage }> = ({ language }) => {
  useEffect(() => {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    document.title = language === 'zh' ? 'FactorForge — 因子智研平台' : 'FactorForge — Quant Research OS';
    const root = document.getElementById('root');
    if (!root) return;
    translateNode(root, language);
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'characterData') translateNode(mutation.target, language);
        mutation.addedNodes.forEach((node) => translateNode(node, language));
        if (mutation.type === 'attributes') translateNode(mutation.target, language);
      }
    });
    observer.observe(root, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: TRANSLATED_ATTRIBUTES });
    return () => observer.disconnect();
  }, [language]);
  return null;
};

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<AppLanguage>(() => {
    const saved = localStorage.getItem('quantaalpha_language');
    return saved === 'en' ? 'en' : 'zh';
  });
  const setLanguage = (next: AppLanguage) => {
    localStorage.setItem('quantaalpha_language', next);
    setLanguageState(next);
  };
  const value = useMemo(() => ({
    language,
    setLanguage,
    toggleLanguage: () => setLanguage(language === 'zh' ? 'en' : 'zh'),
  }), [language]);
  return (
    <LanguageContext.Provider value={value}>
      <AutoTranslator language={language} />
      {children}
    </LanguageContext.Provider>
  );
};

export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('useLanguage must be used inside LanguageProvider');
  return context;
}
