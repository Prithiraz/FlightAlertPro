import { createContext, useContext, useState, useEffect } from 'react';
import { listWorkspaces } from './api';

const WorkspaceContext = createContext(null);

export function WorkspaceProvider({ user, children }) {
  const [workspaces, setWorkspaces] = useState([]);
  const [currentWorkspace, setCurrentWorkspaceState] = useState(null);
  const [loading, setLoading] = useState(false);

  // Load workspaces when user is available
  useEffect(() => {
    if (!user) {
      setWorkspaces([]);
      setCurrentWorkspaceState(null);
      return;
    }
    setLoading(true);
    listWorkspaces()
      .then((data) => {
        const list = data.workspaces || [];
        setWorkspaces(list);
        // Restore previously selected workspace from localStorage
        const saved = localStorage.getItem('fap_workspace_id');
        const found = list.find((w) => w.id === saved);
        setCurrentWorkspaceState(found || list[0] || null);
      })
      .catch(() => {
        setWorkspaces([]);
        setCurrentWorkspaceState(null);
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const setCurrentWorkspace = (ws) => {
    setCurrentWorkspaceState(ws);
    if (ws) {
      localStorage.setItem('fap_workspace_id', ws.id);
    } else {
      localStorage.removeItem('fap_workspace_id');
    }
  };

  return (
    <WorkspaceContext.Provider value={{ workspaces, currentWorkspace, setCurrentWorkspace, loading, setWorkspaces }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  return useContext(WorkspaceContext);
}
