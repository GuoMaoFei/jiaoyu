# PageIndex Tutorials: Tree Search and Doc Search

## 1. LLM Tree Search

### Overview
A simple strategy is to use an LLM agent to perform tree search. The process involves giving the LLM the query and the document's tree structure (node hierarchy) to identify potential nodes that likely contain the answer.

### Basic Tree Search Prompt
```python
prompt = f"""
You are given a query and the tree structure of a document.
You need to find all nodes that are likely to contain the answer.
 
Query: {query}
 
Document tree structure: {PageIndex_Tree}
 
Reply in the following JSON format:
{{
  "thinking": ,
  "node_list": [node_id1, node_id2, ...]
}}
"""
```

### Advanced Retrieval
PageIndex uses a combination of LLM tree search and value function-based Monte Carlo Tree Search (MCTS) in its dashboard and retrieval API.

### Integrating User Preference or Expert Knowledge
Unlike vector-based RAG, PageIndex allows incorporating expert knowledge or user preferences by simply adding them to the LLM tree search prompt.

**Enhanced Tree Search with Expert Preference Example:**
```python
prompt = f"""
You are given a question and a tree structure of a document.
You need to find all nodes that are likely to contain the answer.
 
Query: {query}
 
Document tree structure:  {PageIndex_Tree}
 
Expert Knowledge of relevant sections: {Preference}
 
Reply in the following JSON format:
{{
  "thinking": ,
  "node_list": [node_id1, node_id2, ...]
}}
"""
```
**Example Preference:** For 10-K financial reports, if the query mentions "EBITDA adjustments," the system can be instructed to prioritize "Item 7 (MD&A)" and "Item 8 (Financial Statements)."

---

## 2. Hybrid Tree Search

### Limitations of Simple LLM Tree Search
1. **Retrieval Speed**: LLM reasoning can be slower.
2. **Summary-based Node Selection**: Relying solely on node summaries might miss granular details in the original content.

### Value-based Tree Search
This approach, inspired by AlphaGo, uses an AI model to predict a "value" for each node based on chunk-level relevance.
1. **Chunking**: Nodes are divided into smaller chunks.
2. **Vector Search**: The query identifies top-K relevant chunks.
3. **Node Scoring**: Similarity scores of chunks are aggregated to score the parent node.

**Node Scoring Formula:**
$$NodeScore = \frac{1}{\sqrt{N+1}} \sum_{n=1}^N ChunkScore(n)$$
*Where $N$ is the number of chunks. This scoring method rewards nodes with more highly relevant chunks while preventing very large nodes from dominating due to sheer volume.*

### Hybrid Approach
The default method in the PageIndex API combines value-based and LLM-based searches:
- **Parallel Retrieval**: Runs both methods simultaneously.
- **Queue System**: Consolidates unique nodes found by either method.
- **Node Consumer**: Extracts relevant information from the queue.
- **Early Termination**: An LLM agent determines if sufficient information has been gathered to stop early.

---

## 3. Document Search by Metadata

### Target Use Cases
Documents that can be logically distinguished by categories like time, company, or type (e.g., Financial reports, Legal cases, Medical records).

### Pipeline Steps
1. **Tree Generation**: Upload documents to PageIndex to get a `doc_id`.
2. **SQL Setup**: Store `doc_id` alongside metadata in a database.
3. **Query to SQL**: Use an LLM to transform the user's natural language request into a SQL query.
4. **Retrieve**: Use the `doc_id`s identified by the SQL query to perform deep retrieval via the PageIndex API.

---

## 4. Document Search by Semantics

### Procedure for Diverse Documents
1. **Chunking & Embedding**: Convert document chunks into vectors for a vector database, indexed by `doc_id`.
2. **Vector Search**: Retrieve top-K chunks for a query.
3. **Compute Document Score**: Calculate a relevance score for each document using the same formula used for node scoring in Hybrid Search.
4. **Retrieve**: Select the top-scoring `doc_id`s and proceed with the PageIndex retrieval API.

---

## 5. Document Search by Description

### Lightweight Approach
Best for a small number of documents without clear metadata.

### Pipeline Steps
1. **Description Generation**: Generate a concise, one-sentence description for each document based on its tree structure.
   ```python
   prompt = f"""
   You are given a table of contents structure of a document. 
   Your task is to generate a one-sentence description for the document.
       
   Document tree structure: {PageIndex_Tree}
    
   Directly return the description, do not include any other text.
   """
   ```
2. **Search with LLM**: Use an LLM to compare the user query against the list of descriptions and select relevant documents.
   ```python
   prompt = f""" 
   You are given a list of documents with their IDs, names, and descriptions. Select documents relevant to the query.
    
   Query: {query}
    
   Documents: [{"doc_id": "xxx", "doc_name": "...", "doc_description": "..."}]
    
   Response Format: {"thinking": "", "answer": ["doc_id1", "doc_id2"]}
   """
   ```
3. **Retrieve**: Use the selected `doc_id`s with the PageIndex API.
