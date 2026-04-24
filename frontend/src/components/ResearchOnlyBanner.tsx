/** Banner di compliance visibile su OGNI pagina. Non e' rimovibile. */
export function ResearchOnlyBanner() {
  return (
    <div className="bg-warn/10 border-b border-warn/30 text-warn text-xs py-2 px-4 text-center">
      <strong>RESEARCH ONLY</strong> · <strong>PAPER TRADING ONLY</strong> · <strong>NO REAL ORDERS</strong>
      {" · "}Questa piattaforma non invia ordini reali, non si collega a wallet, non gestisce chiavi.
      {" · "}<a href="/compliance" className="underline">Compliance</a>
    </div>
  );
}
