export function formatMopText(mopData) {
  if (!mopData || !mopData.niveles) return { text: '-', subtext: '', alert: false, maxLevel: 0 };
  
  const levels = Object.keys(mopData.niveles).map(Number).filter(l => !isNaN(l) && l >= 2);
  
  if (levels.length === 0) return { text: '-', subtext: '', alert: false, maxLevel: 0 };
  
  const highestNivel = Math.max(...levels);
  
  // Count occurrences of highestNivel
  let highestCount = 0;
  const yearsDict = mopData.niveles[highestNivel];
  if (yearsDict) {
    for (const year in yearsDict) {
      highestCount += yearsDict[year];
    }
  }
  
  const hasInferiores = levels.some(l => l >= 2 && l < highestNivel);
  
  const text = `${highestCount} de nvl${highestNivel}`;
  const subtext = hasInferiores ? 'e inferiores' : '';
  const alert = highestNivel >= 3;
  
  return { text, subtext, alert, maxLevel: highestNivel };
}
