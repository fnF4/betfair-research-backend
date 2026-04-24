export default function CompliancePage() {
  return (
    <article className="prose prose-invert max-w-3xl space-y-4 text-fg">
      <h1 className="text-2xl font-semibold">Compliance</h1>

      <section className="bg-panel border border-line rounded-xl p-5 space-y-2">
        <h2 className="text-lg font-semibold text-accent">Cosa questa piattaforma FA</h2>
        <ul className="list-disc pl-5 text-sm text-muted space-y-1">
          <li>Legge prezzi e order book pubblici via API ufficiale Betfair Exchange (read-only).</li>
          <li>Rileva opportunità di arbitraggio Categoria 1 (cross-book back/lay sulla stessa selection).</li>
          <li>Simula trade paper (back + lay hedge) localmente per misurare fattibilità economica.</li>
          <li>Mostra tutti i risultati su questa dashboard, identica nel look al backend Polymarket.</li>
        </ul>
      </section>

      <section className="bg-panel border border-line rounded-xl p-5 space-y-2">
        <h2 className="text-lg font-semibold text-bad">Cosa NON fa (per design)</h2>
        <ul className="list-disc pl-5 text-sm text-muted space-y-1">
          <li>Non invia ordini reali a Betfair.</li>
          <li>Non usa la session key per `placeOrders`, `replaceOrders`, `cancelOrders`.</li>
          <li>Non usa VPN, proxy o workaround per bypassare regole geografiche.</li>
          <li>Non scrapa il sito web: solo API ufficiali (betfairlightweight SDK).</li>
          <li>Non salva credenziali Betfair in file versionati — solo env var Render.</li>
        </ul>
      </section>

      <section className="bg-panel border border-line rounded-xl p-5 space-y-2">
        <h2 className="text-lg font-semibold">Giurisdizione Italia</h2>
        <p className="text-sm text-muted">
          Betfair Exchange opera in Italia con licenza ADM tramite betfair.it. Questo backend
          è progettato per usare un account verificato betfair.it. La piattaforma è strumento di{" "}
          <strong>ricerca, simulazione ed educazione</strong>: non costituisce invito, raccomandazione
          o consulenza finanziaria. Prima di qualunque uso con capitale reale, l'utente deve
          valutare aspetti fiscali e legali con un professionista.
        </p>
      </section>

      <section className="bg-panel border border-line rounded-xl p-5 space-y-2">
        <h2 className="text-lg font-semibold">Design fail-closed</h2>
        <p className="text-sm text-muted">
          Il modulo di esecuzione live è intenzionalmente <strong>assente</strong> dal repo. La variabile
          <code className="mx-1 text-fg">EXECUTION_MODE</code> accetta solo <code className="text-fg">paper</code> o
          <code className="mx-1 text-fg">disabled_live</code>. Qualunque altro valore fallisce la validazione all'avvio.
        </p>
      </section>

      <section className="bg-panel border border-line rounded-xl p-5 space-y-2">
        <h2 className="text-lg font-semibold">Data sources</h2>
        <ul className="list-disc pl-5 text-sm text-muted space-y-1">
          <li><code className="text-fg">api.betfair.com / api.betfair.it</code> — Exchange Betting API ufficiale (app key richiesta)</li>
          <li><code className="text-fg">identitysso.betfair.com</code> — login interactive / cert-based (sessione)</li>
        </ul>
      </section>
    </article>
  );
}
