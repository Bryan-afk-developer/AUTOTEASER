export function formatMopText(mopData) {
  if (!mopData || !mopData.niveles || !mopData.anios || mopData.anios.length === 0) {
    return { text: '-', subtext: '', alert: false, maxLevel: 0 };
  }
  
  const levels = Object.keys(mopData.niveles).map(Number).filter(l => !isNaN(l) && l >= 2);
  
  if (levels.length === 0) {
    return { text: '1 NORMAL', subtext: 'SIN MOPs NEGATIVOS', alert: false, maxLevel: 0 };
  }
  
  // Sort years descending to find the most recent
  const anios = mopData.anios.map(Number).sort((a, b) => b - a);
  const mostRecentYear = anios[0];
  
  const allTimeHighestLevel = Math.max(...levels);
  
  // Find highest level in the most recent year
  let recentHighestLevel = 0;
  let recentHighestCount = 0;
  for (let l = allTimeHighestLevel; l >= 2; l--) {
    if (mopData.niveles[l] && mopData.niveles[l][mostRecentYear]) {
      recentHighestLevel = l;
      recentHighestCount = mopData.niveles[l][mostRecentYear];
      break;
    }
  }
  
  let text = '';
  let subtext = '';
  
  if (recentHighestLevel >= 2) {
    text = `${recentHighestCount} de nvl${recentHighestLevel}`;
    if (allTimeHighestLevel > recentHighestLevel) {
      subtext = `Antecedente: nvl${allTimeHighestLevel}`;
    } else {
      // Find if there are lower levels in recent year
      const hasInferioresRecent = Object.keys(mopData.niveles).map(Number).some(l => l >= 2 && l < recentHighestLevel && mopData.niveles[l][mostRecentYear]);
      subtext = hasInferioresRecent ? 'e inferiores' : '';
    }
  } else {
    text = `1 NORMAL (${mostRecentYear})`;
    subtext = `Antecedente: nvl${allTimeHighestLevel}`;
  }
  
  const alert = recentHighestLevel >= 3 || allTimeHighestLevel >= 4;
  
  return { text, subtext, alert, maxLevel: recentHighestLevel || allTimeHighestLevel };
}
