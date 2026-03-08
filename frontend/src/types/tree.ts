export interface TreeStoreState {
    currentMaterialId: string | null;
    treeData: any | null; // ECharts format
    nodeStates: Record<string, any>; // { [node_id]: { health_score, is_unlocked, ... } }
    setCurrentMaterial: (id: string) => void;
    setTreeData: (data: any) => void;
    setNodeStates: (states: any) => void;
    updateNodeState: (nodeId: string, newState: any) => void;
}
