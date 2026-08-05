"""
Python 数据结构练习 - 修正运行版
修正点：add_relation 参数顺序改为 (entity1, relation, entity2) 匹配调用方式
"""
from collections import deque, defaultdict, OrderedDict

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val; self.next = next

class LinkedList:
    def __init__(self): self.head = None; self._size = 0
    def append(self, val):
        new = ListNode(val)
        if not self.head: self.head = new
        else:
            cur = self.head
            while cur.next: cur = cur.next
            cur.next = new
        self._size += 1; return self
    def prepend(self, val):
        self.head = ListNode(val, self.head); self._size += 1; return self
    def delete(self, val):
        if not self.head: return False
        if self.head.val == val: self.head = self.head.next; self._size -= 1; return True
        cur = self.head
        while cur.next:
            if cur.next.val == val: cur.next = cur.next.next; self._size -= 1; return True
            cur = cur.next
        return False
    def find(self, val):
        cur = self.head
        while cur:
            if cur.val == val: return cur
            cur = cur.next
        return None
    def to_list(self):
        r = []; cur = self.head
        while cur: r.append(cur.val); cur = cur.next
        return r
    def __len__(self): return self._size
    def __str__(self): return f"LinkedList({self.to_list()})"
    def reverse(self):
        prev = None; cur = self.head
        while cur: nxt = cur.next; cur.next = prev; prev = cur; cur = nxt
        self.head = prev; return self

# 测试链表
ll = LinkedList()
ll.append(1).append(2).append(3); ll.prepend(0)
print(ll); print(f"长度: {len(ll)}"); print(f"查找2: {ll.find(2) is not None}")
ll.delete(2); print(ll)
ll.reverse(); print(f"反转后: {ll}")


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val; self.left = left; self.right = right

class BST:
    def __init__(self): self.root = None
    def insert(self, val):
        def _i(n, v):
            if not n: return TreeNode(v)
            if v < n.val: n.left = _i(n.left, v)
            elif v > n.val: n.right = _i(n.right, v)
            return n
        self.root = _i(self.root, val); return self
    def search(self, val):
        def _s(n, v):
            if not n: return False
            if v == n.val: return True
            return _s(n.left, v) if v < n.val else _s(n.right, v)
        return _s(self.root, val)
    def inorder(self):
        r = []
        def _i(n):
            if n: _i(n.left); r.append(n.val); _i(n.right)
        _i(self.root); return r
    def level_order(self):
        if not self.root: return []
        r = []; q = deque([self.root])
        while q:
            n = q.popleft(); r.append(n.val)
            if n.left: q.append(n.left)
            if n.right: q.append(n.right)
        return r
    def find_min(self):
        if not self.root: return None
        cur = self.root
        while cur.left: cur = cur.left
        return cur.val
    def height(self):
        def _h(n): return 0 if not n else 1 + max(_h(n.left), _h(n.right))
        return _h(self.root)

bst = BST()
for v in [50,30,70,20,40,60,80,10]: bst.insert(v)
print(f"\n中序: {bst.inorder()}"); print(f"层序: {bst.level_order()}")
print(f"查找40: {bst.search(40)}, 查找99: {bst.search(99)}")
print(f"最小值: {bst.find_min()}, 高度: {bst.height()}")


class Graph:
    def __init__(self): self.adj = defaultdict(list)
    def add_edge(self, u, v, directed=False):
        self.adj[u].append(v)
        if not directed: self.adj[v].append(u)
    def bfs(self, start):
        vis = {start}; order = []; q = deque([start])
        while q:
            n = q.popleft(); order.append(n)
            for nb in self.adj[n]:
                if nb not in vis: vis.add(nb); q.append(nb)
        return order
    def dfs(self, start):
        vis = set(); order = []
        def _d(n):
            vis.add(n); order.append(n)
            for nb in self.adj[n]:
                if nb not in vis: _d(nb)
        _d(start); return order
    def dfs_iterative(self, start):
        vis = {start}; order = []; stack = [start]
        while stack:
            n = stack.pop(); order.append(n)
            for nb in reversed(self.adj[n]):
                if nb not in vis: vis.add(nb); stack.append(nb)
        return order
    def has_path(self, u, v):
        if u == v: return True
        vis = {u}; q = deque([u])
        while q:
            n = q.popleft()
            for nb in self.adj[n]:
                if nb == v: return True
                if nb not in vis: vis.add(nb); q.append(nb)
        return False
    def shortest_path(self, start, end):
        if start == end: return [start]
        vis = {start}; parent = {}; q = deque([start])
        while q:
            n = q.popleft()
            for nb in self.adj[n]:
                if nb not in vis:
                    vis.add(nb); parent[nb] = n
                    if nb == end:
                        p = [end]; c = end
                        while c in parent: c = parent[c]; p.append(c)
                        return list(reversed(p))
                    q.append(nb)
        return None

g = Graph()
for u,v in [("A","B"),("B","C"),("A","D"),("B","E"),("C","F"),("D","E"),("E","F")]: g.add_edge(u,v)
print(f"\nBFS(A): {g.bfs('A')}")
print(f"DFS(A): {g.dfs('A')}")
print(f"A到F最短路径: {g.shortest_path('A','F')}")


class LRUCache:
    def __init__(self, cap): self.cap = cap; self.cache = OrderedDict()
    def get(self, key):
        if key not in self.cache: return -1
        self.cache.move_to_end(key); return self.cache[key]
    def put(self, key, val):
        if key in self.cache: self.cache.move_to_end(key)
        self.cache[key] = val
        if len(self.cache) > self.cap: self.cache.popitem(last=False)
    def __str__(self): return f"LRU({self.cap}): {list(self.cache.items())}"

cache = LRUCache(2)
cache.put(1,"d1"); cache.put(2,"d2")
print(f"\n{cache}"); print(f"get(1): {cache.get(1)}"); print(cache)
cache.put(3,"d3"); print(cache); print(f"get(2): {cache.get(2)}")


class KnowledgeGraph:
    def __init__(self): self.graph = Graph(); self.relations = {}
    def add_relation(self, e1, relation, e2):
        """添加知识三元组 (entity1, relation, entity2)"""
        self.graph.add_edge(e1, e2)
        self.relations[(e1, e2)] = relation
        self.relations[(e2, e1)] = f"{relation}(反向)"
    def find_connections(self, entity, max_depth=2):
        if entity not in self.graph.adj: return {}
        vis = {entity: 0}; q = deque([(entity, 0)])
        while q:
            n, d = q.popleft()
            if d >= max_depth: continue
            for nb in self.graph.adj[n]:
                if nb not in vis: vis[nb] = d + 1; q.append((nb, d + 1))
        return vis
    def relation_path(self, start, end):
        path = self.graph.shortest_path(start, end)
        if not path: return f"❌ {start} 与 {end} 无关联"
        r = [start]
        for i in range(len(path)-1):
            rel = self.relations.get((path[i], path[i+1]), "关联")
            r.append(f" --[{rel}]--> {path[i+1]}")
        return "".join(r)
    def all_entities(self): return list(self.graph.adj.keys())

print("\n" + "="*60)
print("🧠 简易知识图谱引擎演示")
print("="*60)
kg = KnowledgeGraph()
kg.add_relation("机器学习","包含","深度学习")
kg.add_relation("深度学习","包含","神经网络")
kg.add_relation("深度学习","包含","CNN")
kg.add_relation("深度学习","包含","Transformer")
kg.add_relation("神经网络","基础","感知机")
kg.add_relation("CNN","用于","图像分类")
kg.add_relation("Transformer","用于","NLP")
kg.add_relation("Transformer","是","GPT基础")
kg.add_relation("GPT基础","实例","ChatGPT")
kg.add_relation("机器学习","包含","监督学习")
kg.add_relation("监督学习","算法","逻辑回归")
kg.add_relation("监督学习","算法","随机森林")

connections = kg.find_connections("机器学习", max_depth=2)
for e, d in connections.items():
    print(f"{'  '*d}{'→ ' if d>0 else ''}{e}")
print(f"\n路径1: {kg.relation_path('机器学习', 'ChatGPT')}")
print(f"路径2: {kg.relation_path('机器学习', '图像分类')}")
print(f"路径3: {kg.relation_path('Transformer', '感知机')}")
