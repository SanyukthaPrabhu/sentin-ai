import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface HazardInfo {
  id: string;
  icon: string;
  title: string;
  category: string;
  whatIsIt: string;
  whyItHappens: string;
  warningSigns: string[];
  whatToDo: string[];
  whatNotToDo: string[];
  checklist: string[];
  seekHelp: string;
  resources: string[];
}

const HAZARDS: HazardInfo[] = [
  {
    id: 'flood',
    icon: '🌊',
    title: 'Flooding & Flash Floods',
    category: 'Disaster',
    whatIsIt: 'Flooding is an overflow of water that submerges land that is usually dry. Flash floods are sudden, violent torrents of water that run down streams or sweep through urban channels within minutes of heavy rain.',
    whyItHappens: 'Heavy monsoon rains saturate soil, exceeding soil absorption and lake storage capacity. Deforestation and riverbank erosion speed up run-off.',
    warningSigns: [
      'Continuous torrential rainfall exceeding 50mm within a few hours.',
      'Sudden rises in local canal or lake water levels.',
      'Gurgling noises from drains or reverse flows onto roads.'
    ],
    whatToDo: [
      'Move immediately to higher ground or upper floors of concrete buildings.',
      'Turn off all electrical mains and cooking gas connections before evacuating.',
      'Boil or chlorinate drinking water; floods frequently contaminate pipe networks.'
    ],
    whatNotToDo: [
      'Do NOT walk, swim, or drive through moving flood waters; 6 inches of water can sweep you away.',
      'Do NOT touch electrical equipment while wet or standing in water.',
      'Do NOT consume raw food that has come into contact with floodwater.'
    ],
    checklist: [
      'Pack a 3-day emergency kit (dry food, clean bottled water, flashlight, batteries).',
      'Keep copies of identification cards in a sealed plastic bag.',
      'Procure an emergency medical kit including ORS packets and water purification tablets.',
      'Note emergency helpline numbers (National Disaster Helpline: 1078).'
    ],
    seekHelp: 'Seek medical attention immediately if you experience high fever, open wound infections after contact with flood waters, or severe diarrhea.',
    resources: ['NDMA Safety Portal', 'State Disaster Management Authority Guides']
  },
  {
    id: 'urban_flood',
    icon: '🏢',
    title: 'Urban Flooding',
    category: 'Disaster',
    whatIsIt: 'Urban flooding is the inundation of built environments, caused by excessive rainfall overloading local drainage capacities.',
    whyItHappens: 'Unplanned urban expansion covers natural soil with concrete, preventing rainwater percolation. Clogging of storm drains with plastic wastes restricts runoff.',
    warningSigns: [
      'Severe water logging on main avenues within 20 minutes of rainfall.',
      'Overflowing manholes and blocked street gutters.'
    ],
    whatToDo: [
      'Unclog neighborhood street drains if safe to do so before heavy rainfall.',
      'Elevate valuable home electronics and carpets off floor levels.',
      'Observe local municipal advisories before leaving home.'
    ],
    whatNotToDo: [
      'Do NOT drive vehicles into water-logged underpasses or subways.',
      'Do NOT dispose of household plastic waste in open street drains.'
    ],
    checklist: [
      'Check that apartment rainwater harvesting pits are clear.',
      'Locate emergency wooden planks to block water entry at thresholds.',
      'Keep power banks charged to sustain communication during blackouts.'
    ],
    seekHelp: 'Contact municipal authorities (e.g. BBMP control room) if drainage failures endanger structural foundations.',
    resources: ['National Institute of Disaster Management (NIDM)', 'Local Municipal Corporation Advisories']
  },
  {
    id: 'vector_borne',
    icon: '🦟',
    title: 'Mosquito-Borne Disease Control',
    category: 'Public Health',
    whatIsIt: 'Diseases like Dengue, Malaria, and Chikungunya transmitted via the bites of infected vector mosquitoes (Aedes and Anopheles).',
    whyItHappens: 'Stagnant water bodies left undisturbed for 4-7 days provide breeding grounds for mosquito larvae in warm, humid weather.',
    warningSigns: [
      'Sudden high fever accompanied by severe headache and pain behind the eyes.',
      'Joint swelling and muscle pains.',
      'Appearance of skin rashes 3-4 days after fever onset.'
    ],
    whatToDo: [
      'Drain water from plant pots, tyres, coconut shells, and air coolers weekly.',
      'Use mosquito bed nets and apply DEET/Picaridin repellents on exposed skin.',
      'Wear light-colored, long-sleeved clothing to reduce skin exposure.'
    ],
    whatNotToDo: [
      'Do NOT let fresh water collect uncovered in containers or storage drums.',
      'Do NOT self-medicate with aspirin or ibuprofen for fever; they can worsen bleeding if you have Dengue.'
    ],
    checklist: [
      'Verify window mesh screens are intact and free of holes.',
      'Procure mosquito coils, vaporizers, or repellents.',
      'Examine rooftop water storage tanks to ensure lids fit tightly.'
    ],
    seekHelp: 'Go to a clinic immediately if you observe warning signs of Dengue hemorrhagic fever: gum bleeding, persistent vomiting, or extreme lethargy.',
    resources: ['National Vector Borne Disease Control Programme (NVBDCP)', 'World Health Organization (WHO) Guidelines']
  },
  {
    id: 'water_contamination',
    icon: '🧪',
    title: 'Water Contamination & Cholera',
    category: 'Public Health',
    whatIsIt: 'Diseases like Cholera, Typhoid, and Hepatitis A contracted by consuming food or water contaminated with fecal matter or pathogens.',
    whyItHappens: 'Flooding and leaky sewer pipes mix raw sewage into municipal drinking water networks.',
    warningSigns: [
      'Sudden onset of severe, watery diarrhea (often described as "rice-water stool").',
      'Rapid dehydration, dry mouth, and muscle cramps.'
    ],
    whatToDo: [
      'Boil drinking water vigorously for at least one full minute before cooling and drinking.',
      'Wash hands thoroughly with soap before cooking, eating, or after toilet use.',
      'Ensure all food is cooked thoroughly and served piping hot.'
    ],
    whatNotToDo: [
      'Do NOT drink raw tap water or use untreated ice cubes during flood periods.',
      'Do NOT consume raw or undercooked vegetables and seafood.',
      'Do NOT eat food from roadside vendors showing poor sanitation.'
    ],
    checklist: [
      'Stock chlorine tablets (halazone) to treat water if boiling is not possible.',
      'Maintain oral rehydration salts (ORS) at home.',
      'Clean water storage tanks with bleaching powder twice a year.'
    ],
    seekHelp: 'Seek immediate clinical hydration if a family member develops severe watery diarrhea. Cholera can be fatal within hours if untreated.',
    resources: ['Ministry of Health and Family Welfare', 'WHO Cholera Prevention Factsheet']
  },
  {
    id: 'heat_wave',
    icon: '☀️',
    title: 'Extreme Heat & Heat Waves',
    category: 'Disaster',
    whatIsIt: 'A period of abnormally high temperatures, often with high humidity, exceeding local physiological thresholds.',
    whyItHappens: 'High atmospheric pressure traps hot air close to the ground, suppressing cloud cover and breeze.',
    warningSigns: [
      'Body temperature rising above 38.9°C (102°F).',
      'Dizziness, heavy sweating, rapid heartbeat, or throbbing headache.'
    ],
    whatToDo: [
      'Drink water frequently, even if you do not feel thirsty.',
      'Stay indoors in air-conditioned or well-ventilated spaces during peak hours.',
      'Place cool, wet cloths on your neck and forehead to lower temperature.'
    ],
    whatNotToDo: [
      'Do NOT engage in strenuous outdoor activity between 11 AM and 4 PM.',
      'Do NOT consume alcohol, tea, or carbonated drinks as they accelerate dehydration.',
      'Do NOT leave children or pets inside parked vehicles.'
    ],
    checklist: [
      'Ensure you have dark curtains or window film to block solar radiation.',
      'Stock ORS packets or electrolyte drinks in the pantry.',
      'Verify fans or cooling units are functioning before summer starts.'
    ],
    seekHelp: 'Call emergency medical services immediately if someone exhibits confusion, slurred speech, loss of consciousness, or hot, dry skin (signs of Heat Stroke).',
    resources: ['NDMA Heat Wave Action Plan', 'Indian Meteorological Department (IMD)']
  }
];

export default function AwarenessCenter() {
  const [selectedHazard, setSelectedHazard] = useState<HazardInfo | null>(null);
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem('sentin_awareness_checklist');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const handleToggleCheck = (key: string) => {
    setCheckedItems(prev => {
      const updated = { ...prev, [key]: !prev[key] };
      localStorage.setItem('sentin_awareness_checklist', JSON.stringify(updated));
      return updated;
    });
  };

  const progressPercentage = (hazard: HazardInfo) => {
    const list = hazard.checklist;
    const completed = list.filter(item => checkedItems[`${hazard.id}-${item}`]).length;
    return list.length ? Math.round((completed / list.length) * 100) : 0;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', width: '100%', height: '100%' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>Awareness &amp; Safety Center</h2>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
          Explore official safety guidelines, warning indicators, and checklist preps compiled by disaster response guidelines.
        </p>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: '1.25rem'
      }}>
        {HAZARDS.map(hazard => {
          const progress = progressPercentage(hazard);
          return (
            <motion.div
              key={hazard.id}
              onClick={() => setSelectedHazard(hazard)}
              className="landing-card"
              style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', height: '100%' }}
              whileHover={{ y: -4, borderColor: 'var(--cyan)' }}
              layoutId={`card-${hazard.id}`}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.5rem' }}>{hazard.icon}</span>
                <span style={{
                  fontSize: '0.65rem',
                  fontFamily: 'DM Mono',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  padding: '0.2rem 0.5rem',
                  borderRadius: 12,
                  background: hazard.category === 'Disaster' ? 'rgba(239,68,68,0.1)' : 'rgba(14,165,233,0.1)',
                  color: hazard.category === 'Disaster' ? 'var(--red)' : 'var(--cyan)',
                  border: `1px solid ${hazard.category === 'Disaster' ? 'rgba(239,68,68,0.2)' : 'rgba(14,165,233,0.2)'}`
                }}>
                  {hazard.category}
                </span>
              </div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.5rem' }}>{hazard.title}</h3>
              <p style={{
                fontSize: '0.78rem',
                color: 'var(--text-muted)',
                lineHeight: 1.4,
                marginBottom: '1rem',
                flex: 1
              }}>
                {hazard.whatIsIt.substring(0, 100)}...
              </p>
              
              {/* Progress bar */}
              <div style={{ marginTop: 'auto' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  <span>Prep Checklist</span>
                  <span>{progress}%</span>
                </div>
                <div style={{ width: '100%', height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${progress}%`, height: '100%', background: progress === 100 ? 'var(--green)' : 'var(--cyan)', transition: 'width 0.3s ease' }} />
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Detail overlay modal */}
      <AnimatePresence>
        {selectedHazard && (
          <div style={{
            position: 'fixed', inset: 0, background: 'rgba(5,7,12,0.85)',
            backdropFilter: 'blur(8px)', zIndex: 2000, display: 'flex',
            alignItems: 'center', justifyContent: 'center', padding: '1rem'
          }}>
            <motion.div
              layoutId={`card-${selectedHazard.id}`}
              style={{
                width: '100%', maxWidth: 750, maxHeight: '90vh',
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 16, overflowY: 'auto', display: 'flex', flexDirection: 'column',
                position: 'relative', boxShadow: '0 20px 40px rgba(0,0,0,0.5)'
              }}
            >
              {/* Modal header */}
              <div style={{
                padding: '1.5rem', borderBottom: '1px solid var(--border)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                position: 'sticky', top: 0, background: 'var(--bg-card)', zIndex: 10
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ fontSize: '2rem' }}>{selectedHazard.icon}</span>
                  <div>
                    <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>{selectedHazard.title}</h3>
                    <span style={{ fontSize: '0.7rem', color: 'var(--cyan)', fontFamily: 'DM Mono' }}>
                      {selectedHazard.category.toUpperCase()} ADVISORY
                    </span>
                  </div>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={() => setSelectedHazard(null)}
                  style={{ borderRadius: '50%', width: 36, height: 36, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  ✕
                </button>
              </div>

              {/* Modal content */}
              <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                
                <div>
                  <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--cyan)', fontFamily: 'DM Mono', marginBottom: '0.4rem' }}>
                    What is it?
                  </h4>
                  <p style={{ fontSize: '0.85rem', lineHeight: 1.5, color: 'var(--text-secondary)' }}>{selectedHazard.whatIsIt}</p>
                </div>

                <div>
                  <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--cyan)', fontFamily: 'DM Mono', marginBottom: '0.4rem' }}>
                    Why does it happen?
                  </h4>
                  <p style={{ fontSize: '0.85rem', lineHeight: 1.5, color: 'var(--text-secondary)' }}>{selectedHazard.whyItHappens}</p>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ background: 'rgba(16,185,129,0.03)', border: '1px solid rgba(16,185,129,0.1)', borderRadius: 8, padding: '1rem' }}>
                    <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--green)', fontFamily: 'DM Mono', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                      🟢 What to DO
                    </h4>
                    <ul style={{ fontSize: '0.8rem', paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', color: 'var(--text-secondary)' }}>
                      {selectedHazard.whatToDo.map((item, idx) => <li key={idx}>{item}</li>)}
                    </ul>
                  </div>

                  <div style={{ background: 'rgba(239,68,68,0.03)', border: '1px solid rgba(239,68,68,0.1)', borderRadius: 8, padding: '1rem' }}>
                    <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--red)', fontFamily: 'DM Mono', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                      🔴 What NOT to DO
                    </h4>
                    <ul style={{ fontSize: '0.8rem', paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', color: 'var(--text-secondary)' }}>
                      {selectedHazard.whatNotToDo.map((item, idx) => <li key={idx}>{item}</li>)}
                    </ul>
                  </div>
                </div>

                {/* Warning Signs */}
                <div>
                  <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--cyan)', fontFamily: 'DM Mono', marginBottom: '0.5rem' }}>
                    ⚠️ Early Warning Signs
                  </h4>
                  <ul style={{ fontSize: '0.82rem', paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', color: 'var(--text-secondary)' }}>
                    {selectedHazard.warningSigns.map((sign, idx) => <li key={idx}>{sign}</li>)}
                  </ul>
                </div>

                {/* Interactive checklist */}
                <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)', borderRadius: 8, padding: '1rem' }}>
                  <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--cyan)', fontFamily: 'DM Mono', marginBottom: '0.75rem', display: 'flex', justifyContent: 'space-between' }}>
                    <span>📦 Preparation Checklist</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      ({selectedHazard.checklist.filter(item => checkedItems[`${selectedHazard.id}-${item}`]).length} of {selectedHazard.checklist.length} prepped)
                    </span>
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    {selectedHazard.checklist.map((item, idx) => {
                      const key = `${selectedHazard.id}-${item}`;
                      const isChecked = !!checkedItems[key];
                      return (
                        <label
                          key={idx}
                          style={{
                            display: 'flex', alignItems: 'center', gap: '0.75rem',
                            fontSize: '0.82rem', color: isChecked ? 'var(--text-muted)' : 'var(--text-primary)',
                            cursor: 'pointer', padding: '0.4rem 0.6rem', borderRadius: 4,
                            background: isChecked ? 'rgba(255,255,255,0.01)' : 'rgba(255,255,255,0.03)',
                            textDecoration: isChecked ? 'line-through' : 'none',
                            transition: 'all 0.15s ease'
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => handleToggleCheck(key)}
                            style={{
                              width: 16, height: 16, cursor: 'pointer',
                              accentColor: 'var(--cyan)'
                            }}
                          />
                          {item}
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* Clinical Help */}
                <div style={{ borderLeft: '3px solid var(--amber)', paddingLeft: '0.75rem', margin: '0.2rem 0' }}>
                  <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--amber)', fontFamily: 'DM Mono', marginBottom: '0.2rem' }}>
                    When to Seek Medical Help
                  </h4>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{selectedHazard.seekHelp}</p>
                </div>

                {/* Official references */}
                <div>
                  <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontFamily: 'DM Mono', marginBottom: '0.4rem' }}>
                    Official Resources
                  </h4>
                  <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                    {selectedHazard.resources.map((res, idx) => (
                      <span key={idx} style={{
                        fontSize: '0.72rem', color: 'var(--cyan)', background: 'rgba(0,229,255,0.05)',
                        border: '1px solid rgba(0,229,255,0.15)', padding: '0.25rem 0.6rem', borderRadius: 20
                      }}>
                        🔗 {res}
                      </span>
                    ))}
                  </div>
                </div>

              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
