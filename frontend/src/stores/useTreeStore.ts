import { create } from 'zustand';
import { type TreeStoreState } from '../types/tree';

export const useTreeStore = create<TreeStoreState>((set) => ({
    currentMaterialId: null,
    treeData: null,
    nodeStates: {},
    setCurrentMaterial: (id) => set({ currentMaterialId: id }),
    setTreeData: (data) => set({ treeData: data }),
    setNodeStates: (states) => set({ nodeStates: states }),
    updateNodeState: (nodeId, newState) =>
        set((state) => ({
            nodeStates: {
                ...state.nodeStates,
                [nodeId]: { ...(state.nodeStates[nodeId] || {}), ...newState }
            }
        })),
}));
