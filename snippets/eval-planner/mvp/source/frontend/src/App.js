import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Editor from "@monaco-editor/react";

const API_BASE = '/api/rules';

function App() {
    const [rules, setRules] = useState([]);
    const [selectedRule, setSelectedRule] = useState(null);
    const [isEditing, setIsEditing] = useState(false);

    // Form State
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        code_content: 'def evaluate(ctx):\n    return {"score": 1, "passed": True}'
    });

    useEffect(() => {
        fetchRules();
    }, []);

    const fetchRules = async () => {
        try {
            const res = await axios.get(API_BASE);
            setRules(res.data);
        } catch (err) {
            console.error("Failed to fetch rules", err);
        }
    };

    const handleSelectRule = (rule) => {
        setSelectedRule(rule);
        setFormData({
            name: rule.name,
            description: rule.description || '',
            code_content: rule.code_content
        });
        setIsEditing(false); // View mode first
    };

    const handleCreateNew = () => {
        setSelectedRule(null);
        setFormData({
            name: '',
            description: '',
            code_content: 'def evaluate(ctx):\n    return {"score": 1, "passed": True}'
        });
        setIsEditing(true);
    };

    const handleSave = async () => {
        try {
            if (selectedRule && selectedRule.id) {
                // Update
                await axios.put(`${API_BASE}/${selectedRule.id}`, formData);
            } else {
                // Create
                await axios.post(API_BASE, formData);
            }
            fetchRules();
            setIsEditing(false);
            setSelectedRule(null);
        } catch (err) {
            alert("Error saving rule: " + err.message);
        }
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();
        if (!window.confirm("Are you sure?")) return;
        try {
            await axios.delete(`${API_BASE}/${id}`);
            fetchRules();
            if (selectedRule?.id === id) setSelectedRule(null);
        } catch (err) {
            alert("Error deleting rule");
        }
    };

    return (
        <div style={{ display: 'flex', height: '100vh', fontFamily: 'sans-serif' }}>
            {/* Sidebar List */}
            <div style={{ width: '300px', borderRight: '1px solid #ccc', padding: '1rem', overflowY: 'auto' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h2 style={{ margin: 0 }}>Rules</h2>
                    <button onClick={handleCreateNew} style={{ padding: '0.5rem 1rem', background: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>+ New</button>
                </div>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                    {rules.map(rule => (
                        <li
                            key={rule.id}
                            onClick={() => handleSelectRule(rule)}
                            style={{
                                padding: '0.75rem',
                                borderBottom: '1px solid #eee',
                                cursor: 'pointer',
                                background: selectedRule?.id === rule.id ? '#f0f7ff' : 'transparent'
                            }}
                        >
                            <div style={{ fontWeight: 'bold' }}>{rule.name}</div>
                            <div style={{ fontSize: '0.8rem', color: '#666' }}>{new Date(rule.updated_at).toLocaleDateString()}</div>
                            <button
                                onClick={(e) => handleDelete(rule.id, e)}
                                style={{ float: 'right', marginTop: '-20px', color: 'red', border: 'none', background: 'none' }}
                            >
                                ×
                            </button>
                        </li>
                    ))}
                </ul>
            </div>

            {/* Main Content */}
            <div style={{ flex: 1, padding: '2rem', display: 'flex', flexDirection: 'column' }}>
                {(isEditing || selectedRule) ? (
                    <>
                        <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between' }}>
                            <div>
                                {isEditing ? (
                                    <button onClick={handleSave} style={{ marginRight: '1rem', padding: '0.5rem 1rem', background: '#28a745', color: 'white', border: 'none', borderRadius: '4px' }}>Save Rule</button>
                                ) : (
                                    <button onClick={() => setIsEditing(true)} style={{ marginRight: '1rem', padding: '0.5rem 1rem', background: '#ffc107', border: 'none', borderRadius: '4px' }}>Edit Rule</button>
                                )}
                                <button onClick={() => { setSelectedRule(null); setIsEditing(false); }} style={{ padding: '0.5rem 1rem', border: '1px solid #ccc', borderRadius: '4px' }}>Cancel</button>
                            </div>
                        </div>

                        <div style={{ display: 'flex', gap: '2rem', flex: 1 }}>
                            {/* Metadata Form */}
                            <div style={{ width: '300px' }}>
                                <div style={{ marginBottom: '1rem' }}>
                                    <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>Name</label>
                                    <input
                                        type="text"
                                        value={formData.name}
                                        onChange={e => setFormData({ ...formData, name: e.target.value })}
                                        disabled={!isEditing}
                                        style={{ width: '100%', padding: '0.5rem' }}
                                    />
                                </div>
                                <div style={{ marginBottom: '1rem' }}>
                                    <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>Description</label>
                                    <textarea
                                        value={formData.description}
                                        onChange={e => setFormData({ ...formData, description: e.target.value })}
                                        disabled={!isEditing}
                                        style={{ width: '100%', padding: '0.5rem', height: '100px' }}
                                    />
                                </div>
                            </div>

                            {/* Code Editor */}
                            <div style={{ flex: 1, border: '1px solid #ccc' }}>
                                <Editor
                                    height="100%"
                                    defaultLanguage="python"
                                    value={formData.code_content}
                                    onChange={value => setFormData({ ...formData, code_content: value })}
                                    options={{ readOnly: !isEditing, minimap: { enabled: false } }}
                                    theme="vs-dark"
                                />
                            </div>
                        </div>
                    </>
                ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#999' }}>
                        Select a rule or create a new one to get started.
                    </div>
                )}
            </div>
        </div>
    );
}

export default App;
