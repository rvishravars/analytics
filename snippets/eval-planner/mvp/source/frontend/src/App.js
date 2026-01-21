import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Editor from '@monaco-editor/react';
import './App.css';

const API_BASE = '/api/rules';
const AGENT_API = '/api/agents';
const JOB_API = '/api/jobs';

const DEFAULTS = {
    PYTHON: 'async def evaluate(agent_url, auth_config, config):\n    import httpx\n    async with httpx.AsyncClient() as client:\n        res = await client.get(f"{agent_url}/health")\n        return {"score": 1 if res.status_code == 200 else 0, "passed": res.status_code == 200}'
};

function App() {
    const [activeTab, setActiveTab] = useState('RULES');

    // State
    const [rules, setRules] = useState([]);
    const [selectedRule, setSelectedRule] = useState(null);
    const [isEditingRule, setIsEditingRule] = useState(false);
    const [ruleFormData, setRuleFormData] = useState({ name: '', description: '', code_content: DEFAULTS.PYTHON, rule_type: 'PYTHON' });

    const [agents, setAgents] = useState([]);
    const [isEditingAgent, setIsEditingAgent] = useState(false);
    const [agentFormData, setAgentFormData] = useState({ name: '', url: '', auth_config: '{\n  "headers": {\n    "Authorization": "Bearer <token>"\n  }\n}' });

    const [jobs, setJobs] = useState([]);
    const [isCreatingJob, setIsCreatingJob] = useState(false);
    const [jobFormData, setJobFormData] = useState({ rule_id: '', agent_id: '' });

    useEffect(() => {
        fetchRules();
        fetchAgents();
        fetchJobs();
    }, []);

    useEffect(() => {
        let interval;
        if (activeTab === 'JOBS') {
            interval = setInterval(fetchJobs, 3000);
        }
        return () => clearInterval(interval);
    }, [activeTab]);

    const fetchRules = async () => { try { const res = await axios.get(API_BASE); setRules(res.data); } catch (e) { console.error(e); } };
    const fetchAgents = async () => { try { const res = await axios.get(AGENT_API); setAgents(res.data); } catch (e) { console.error(e); } };
    const fetchJobs = async () => { try { const res = await axios.get(JOB_API); setJobs(res.data); } catch (e) { console.error(e); } };

    // --- Rule Actions ---
    const handleCreateRule = () => {
        setSelectedRule(null);
        setRuleFormData({ name: '', description: '', code_content: DEFAULTS.PYTHON, rule_type: 'PYTHON' });
        setIsEditingRule(true);
    };

    const handleSaveRule = async () => {
        try {
            if (selectedRule?.id) await axios.put(`${API_BASE}/${selectedRule.id}`, ruleFormData);
            else await axios.post(API_BASE, ruleFormData);
            fetchRules(); setIsEditingRule(false);
        } catch (e) { alert(e.message); }
    };

    const handleDeleteRule = async (id, e) => {
        e.stopPropagation();
        if (!window.confirm("Delete?")) return;
        try { await axios.delete(`${API_BASE}/${id}`); fetchRules(); if (selectedRule?.id === id) setSelectedRule(null); } catch (e) { alert(e); }
    };

    // --- Agent Actions ---
    const handleSaveAgent = async () => {
        try {
            const payload = { ...agentFormData, auth_config: JSON.parse(agentFormData.auth_config) };
            await axios.post(AGENT_API, payload);
            fetchAgents(); setIsEditingAgent(false);
        } catch (e) { alert("Invalid JSON or Server Error"); }
    };

    // --- Job Actions ---
    const handleInitJob = (rId = '', aId = '') => {
        setJobFormData({ rule_id: rId, agent_id: aId });
        setIsCreatingJob(true);
    };

    const handleSubmitJob = async () => {
        try {
            await axios.post(JOB_API, jobFormData);
            fetchJobs(); setIsCreatingJob(false); setActiveTab('JOBS');
        } catch (e) { alert(e.message); }
    };

    return (
        <div className="app-container">
            {/* Navbar */}
            <div className="top-nav">
                <div className="brand">Agentic Eval</div>
                <button className={`nav-btn ${activeTab === 'RULES' ? 'active' : ''}`} onClick={() => setActiveTab('RULES')}>Rules</button>
                <button className={`nav-btn ${activeTab === 'AGENTS' ? 'active' : ''}`} onClick={() => setActiveTab('AGENTS')}>Agents</button>
                <button className={`nav-btn ${activeTab === 'JOBS' ? 'active' : ''}`} onClick={() => setActiveTab('JOBS')}>Jobs</button>
            </div>

            {/* Rules Tab */}
            {activeTab === 'RULES' && (
                <div className="content-area">
                    <div className="sidebar">
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', alignItems: 'center' }}>
                            <h3 style={{ margin: 0 }}>Rules</h3>
                            <button className="btn btn-primary" onClick={handleCreateRule}>+ New</button>
                        </div>
                        {rules.map(r => (
                            <div key={r.id} className={`list-item ${selectedRule?.id === r.id ? 'selected' : ''}`} onClick={() => { setSelectedRule(r); setIsEditingRule(false); setRuleFormData(r); }}>
                                <div style={{ fontWeight: '600' }}>{r.name}</div>
                                <small style={{ color: 'var(--text-secondary)' }}>{r.rule_type}</small>
                                <button className="btn btn-danger" style={{ padding: '2px 8px', float: 'right' }} onClick={(e) => handleDeleteRule(r.id, e)}>×</button>
                            </div>
                        ))}
                    </div>
                    <div className="main-panel">
                        {(selectedRule || isEditingRule) ? (
                            <>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                                    <div>
                                        {isEditingRule ?
                                            <button className="btn btn-success" onClick={handleSaveRule}>Save Rule</button> :
                                            <button className="btn btn-primary" onClick={() => setIsEditingRule(true)}>Edit Rule</button>
                                        }
                                        {!isEditingRule && <button className="btn btn-secondary" style={{ marginLeft: '1rem' }} onClick={() => handleInitJob(selectedRule.id)}>▶ Run Eval</button>}
                                    </div>
                                    <button className="btn btn-secondary" onClick={() => { setSelectedRule(null); setIsEditingRule(false); }}>Close</button>
                                </div>
                                <div style={{ display: 'flex', gap: '2rem', height: '100%' }}>
                                    <div style={{ width: '350px' }}>
                                        <label className="label">Name</label>
                                        <input className="input-field" value={ruleFormData.name} disabled={!isEditingRule} onChange={e => setRuleFormData({ ...ruleFormData, name: e.target.value })} />
                                        <label className="label">Description</label>
                                        <textarea className="input-field" style={{ height: '120px' }} value={ruleFormData.description} disabled={!isEditingRule} onChange={e => setRuleFormData({ ...ruleFormData, description: e.target.value })} />
                                    </div>
                                    <div style={{ flex: 1, border: '1px solid var(--border-color)', borderRadius: '0.5rem', overflow: 'hidden' }}>
                                        <Editor height="100%" language="python" theme="vs-dark" value={ruleFormData.code_content} options={{ readOnly: !isEditingRule }} onChange={v => setRuleFormData({ ...ruleFormData, code_content: v })} />
                                    </div>
                                </div>
                            </>
                        ) : <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)' }}>Select a rule to view details</div>}
                    </div>
                </div>
            )}

            {/* Agents Tab */}
            {activeTab === 'AGENTS' && (
                <div className="main-panel">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                        <h2 style={{ margin: 0 }}>Agent Registry</h2>
                        <button className="btn btn-primary" onClick={() => { setAgentFormData({ name: '', url: '', auth_config: '{\n}' }); setIsEditingAgent(true); }}>+ Register Agent</button>
                    </div>

                    {isEditingAgent && (
                        <div className="card">
                            <h3>New Agent Details</h3>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                <div>
                                    <label className="label">Agent Name</label>
                                    <input className="input-field" value={agentFormData.name} onChange={e => setAgentFormData({ ...agentFormData, name: e.target.value })} placeholder="e.g. Staging V2" />
                                </div>
                                <div>
                                    <label className="label">Base URL</label>
                                    <input className="input-field" value={agentFormData.url} onChange={e => setAgentFormData({ ...agentFormData, url: e.target.value })} placeholder="https://api.example.com" />
                                </div>
                            </div>
                            <label className="label">Auth Configuration (JSON)</label>
                            <textarea className="input-field" style={{ height: '100px', fontFamily: 'monospace' }} value={agentFormData.auth_config} onChange={e => setAgentFormData({ ...agentFormData, auth_config: e.target.value })} />
                            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                                <button className="btn btn-success" onClick={handleSaveAgent}>Save Agent</button>
                                <button className="btn btn-secondary" onClick={() => setIsEditingAgent(false)}>Cancel</button>
                            </div>
                        </div>
                    )}

                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>URL</th>
                                <th>Registered</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {agents.map(a => (
                                <tr key={a.id}>
                                    <td><span style={{ fontWeight: 600 }}>{a.name}</span></td>
                                    <td><code style={{ background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>{a.url}</code></td>
                                    <td>{new Date(a.created_at).toLocaleDateString()}</td>
                                    <td><button className="btn btn-primary" style={{ fontSize: '0.8rem', padding: '0.25rem 0.75rem' }} onClick={() => handleInitJob('', a.id)}>▶ Eval</button></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Jobs Tab */}
            {activeTab === 'JOBS' && (
                <div className="main-panel">
                    <h2 style={{ marginBottom: '2rem' }}>Evaluation Jobs</h2>
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Job ID</th>
                                <th>Status</th>
                                <th>Rule</th>
                                <th>Agent</th>
                                <th>Started</th>
                            </tr>
                        </thead>
                        <tbody>
                            {jobs.map(j => (
                                <tr key={j.id}>
                                    <td><code style={{ color: 'var(--accent-color)' }}>{j.id.split('-')[0]}</code></td>
                                    <td>
                                        <span style={{
                                            padding: '4px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 'bold',
                                            background: j.status === 'COMPLETED' ? 'rgba(34,197,94,0.2)' : 'rgba(234,179,8,0.2)',
                                            color: j.status === 'COMPLETED' ? '#4ade80' : '#facc15'
                                        }}>
                                            {j.status}
                                        </span>
                                    </td>
                                    <td>{j.rule_id ? j.rule_id.split('-')[0] : 'N/A'}</td>
                                    <td>{j.agent_id ? j.agent_id.split('-')[0] : 'N/A'}</td>
                                    <td>{new Date(j.created_at).toLocaleString()}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Run Job Modal */}
            {isCreatingJob && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <h3>Start Evaluation Job</h3>
                        <label className="label">Select Agent</label>
                        <select className="input-field" value={jobFormData.agent_id} onChange={e => setJobFormData({ ...jobFormData, agent_id: e.target.value })}>
                            <option value="">Choose Agent</option>
                            {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                        </select>
                        <label className="label">Select Rule</label>
                        <select className="input-field" value={jobFormData.rule_id} onChange={e => setJobFormData({ ...jobFormData, rule_id: e.target.value })}>
                            <option value="">Choose Rule</option>
                            {rules.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                        </select>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '2rem' }}>
                            <button className="btn btn-secondary" onClick={() => setIsCreatingJob(false)}>Cancel</button>
                            <button className="btn btn-primary" onClick={handleSubmitJob} disabled={!jobFormData.agent_id || !jobFormData.rule_id}>Start Job</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;
