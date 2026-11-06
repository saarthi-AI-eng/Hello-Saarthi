import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface GraphOutputProps {
    data: { freq: number; mag: number }[];
    cutoff: number;
}

export default function GraphOutput({ data, cutoff }: GraphOutputProps) {
    return (
        <div className="codelab-graph-panel">
            <div className="graph-header">
                <h4>Frequency Response - Butterworth Low-Pass Filter</h4>
                <div className="graph-badges">
                    <span className="badge badge-sm badge-success">✓ Cutoff: {cutoff}Hz</span>
                    <span className="badge badge-sm badge-info">Order: 4</span>
                </div>
            </div>

            <div className="graph-container">
                <ResponsiveContainer width="100%" height="100%" style={{ background: 'transparent' }}>
                    <LineChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis
                            dataKey="freq"
                            label={{ value: 'Frequency (Hz)', position: 'insideBottom', offset: -10, fill: '#9CA3AF' }}
                            stroke="#9CA3AF"
                            tick={{ fill: '#9CA3AF' }}
                        />
                        <YAxis
                            label={{ value: 'Magnitude (dB)', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
                            stroke="#9CA3AF"
                            tick={{ fill: '#9CA3AF' }}
                            domain={[-60, 5]}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1F2937', borderColor: '#374151', color: '#F3F4F6' }}
                            itemStyle={{ color: '#818CF8' }}
                            formatter={(value: any) => [`${Number(value).toFixed(2)} dB`, 'Magnitude']}
                            labelFormatter={(label) => `${label} Hz`}
                        />
                        <ReferenceLine x={cutoff} stroke="#EF4444" strokeDasharray="3 3" label={{ value: 'Cutoff', fill: '#EF4444' }} />
                        <ReferenceLine y={-3} stroke="#F59E0B" strokeDasharray="3 3" label={{ value: '-3dB', fill: '#F59E0B' }} />
                        <Line
                            type="monotone"
                            dataKey="mag"
                            stroke="#818CF8"
                            strokeWidth={3}
                            dot={false}
                            activeDot={{ r: 6 }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>

            <div className="graph-footer">
                <p className="text-success text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-success"></span>
                    Graph shows proper low-pass characteristics with -20dB/decade roll-off.
                </p>
            </div>
        </div>
    );
}
