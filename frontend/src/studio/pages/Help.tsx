import { card, PageTitle, useTitle } from '../ui'

const QA: [string, string][] = [
  ['What does this do?', 'You upload a table (CSV) and choose the column you want to predict, for example “will this customer leave?” or “what will this house sell for?”. The platform tries many models, keeps the ones with the best balance of accuracy, prediction speed and file size, and gives you the winners to download or use online.'],
  ['What is the “Pareto” or “best trade-offs” idea?', 'A tiny, fast model is rarely the most accurate, and the most accurate one is rarely tiny. A model is “Pareto-optimal” when nothing else is at least as good on score, speed and size and also better on one of them. You choose from that short list based on what matters to you.'],
  ['How are scores measured fairly?', 'Your rows are split three ways: training, validation (used to compare models during the search) and a test set that is never touched until the end. The “test” score is the honest one.'],
  ['What data works best?', 'A header row, one row per example, at least ~100 rows (30 is the minimum), and a target column with few missing values. Numbers and short categories work well. Free text and ID-like columns are ignored automatically.'],
  ['Why was a column ignored?', 'Columns with a single value, or hundreds of distinct text values (names, IDs, notes), can’t be learned from reliably, so they are skipped. The dataset page lists them.'],
  ['What are the limits?', 'Free accounts: a few datasets and experiments, files up to a few MB, one experiment at a time, with a time limit. Exact numbers are on your Overview page.'],
  ['What does “ms per 1,000 rows” mean?', 'How long the model needs to make 1,000 predictions on the server. Lower is better when you need quick answers or run on small devices.'],
  ['How do I use the model outside the website?', 'Download model.joblib and predict.py, install the packages listed next to the download button (same scikit-learn version), then run: python predict.py your_new_data.csv.'],
  ['Can I trust the results?', 'Treat them as a strong starting point. Check the baseline comparison, look at which columns mattered, and test on fresh real-world data before important decisions.'],
  ['What about image or GPU deep-learning search?', 'This site covers tabular data on CPU. The repository also contains a research-grade GPU neural-architecture-search platform; see the project README.'],
]

export function Help() {
  useTitle('Help')
  return (
    <div className="max-w-3xl">
      <PageTitle title="Help & FAQ" sub="Short answers to the questions people ask most." />
      <div className="space-y-2">
        {QA.map(([q, a]) => (
          <details key={q} className={`group ${card} !py-3`}><summary className="cursor-pointer list-none flex items-center justify-between gap-3 text-[14px] font-medium text-gray-900">{q}<span className="text-blue-500 transition-transform group-open:rotate-45 text-[18px]" aria-hidden="true">+</span></summary>
            <p className="text-[13px] text-gray-600 mt-2 leading-relaxed">{a}</p></details>
        ))}
      </div>
    </div>
  )
}
