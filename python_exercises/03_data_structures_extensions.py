"""
数据结构扩展练习 —— 编程小悟的作答
=====================================
完成 03_data_structures.py 末尾的 6 道扩展练习
"""

import heapq
from collections import deque, defaultdict


# =============================================================================
# 扩展 1：双向链表（DoublyLinkedList）
# =============================================================================
class DoublyListNode:
    def __init__(self, val=0, prev=None, next=None):
        self.val = val; self.prev = prev; self.next = next


class DoublyLinkedList:
    """双向链表：O(1) 头尾插入删除，支持反向遍历"""

    def __init__(self):
        self.head = None; self.tail = None; self._size = 0

    def append(self, val):
        new = DoublyListNode(val, self.tail, None)
        if not self.head:
            self.head = self.tail = new
        else:
            self.tail.next = new; self.tail = new
        self._size += 1; return self

    def prepend(self, val):
        new = DoublyListNode(val, None, self.head)
        if not self.head:
            self.head = self.tail = new
        else:
            self.head.prev = new; self.head = new
        self._size += 1; return self

    def delete(self, val):
        cur = self.head
        while cur:
            if cur.val == val:
                if cur.prev: cur.prev.next = cur.next
                else: self.head = cur.next
                if cur.next: cur.next.prev = cur.prev
                else: self.tail = cur.prev
                self._size -= 1; return True
            cur = cur.next
        return False

    def to_list(self):
        r = []; cur = self.head
        while cur: r.append(cur.val); cur = cur.next
        return r

    def to_list_reverse(self):
        """反向遍历：从尾部到头部"""
        r = []; cur = self.tail
        while cur: r.append(cur.val); cur = cur.prev
        return r

    def __len__(self): return self._size
    def __str__(self): return f"DoublyLinkedList({self.to_list()})"


def test_doubly():
    print("=== 扩展1: 双向链表 ===")
    dl = DoublyLinkedList()
    dl.append(1).append(2).append(3)
    dl.prepend(0)
    print(f"  正向: {dl}")
    print(f"  反向: {dl.to_list_reverse()}")
    print(f"  长度: {len(dl)}")
    dl.delete(2)
    print(f"  删除2后: {dl}")
    dl.delete(0)
    print(f"  删除0(头)后: {dl}")
    dl.delete(3)
    print(f"  删除3(尾)后: {dl}")


# =============================================================================
# 扩展 2：二叉树非递归遍历（用栈模拟递归）
# =============================================================================
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val; self.left = left; self.right = right


def inorder_iterative(root):
    """非递归中序遍历：左→根→右"""
    result = []; stack = []; cur = root
    while cur or stack:
        while cur:  # 一路向左压栈
            stack.append(cur); cur = cur.left
        cur = stack.pop()
        result.append(cur.val)
        cur = cur.right  # 转向右子树
    return result


def preorder_iterative(root):
    """非递归前序遍历：根→左→右"""
    if not root: return []
    result = []; stack = [root]
    while stack:
        node = stack.pop()
        result.append(node.val)
        if node.right: stack.append(node.right)  # 先压右（后出）
        if node.left: stack.append(node.left)    # 再压左（先出）
    return result


def postorder_iterative(root):
    """非递归后序遍历：左→右→根（用双栈法）"""
    if not root: return []
    result = []; stack1 = [root]; stack2 = []
    while stack1:
        node = stack1.pop()
        stack2.append(node)
        if node.left: stack1.append(node.left)
        if node.right: stack1.append(node.right)
    while stack2:
        result.append(stack2.pop().val)
    return result


def test_tree_iterative():
    print("\n=== 扩展2: 非递归树遍历 ===")
    # 构建树:
    #        1
    #       / \
    #      2   3
    #     / \   \
    #    4   5   6
    root = TreeNode(1)
    root.left = TreeNode(2)
    root.right = TreeNode(3)
    root.left.left = TreeNode(4)
    root.left.right = TreeNode(5)
    root.right.right = TreeNode(6)

    print(f"  前序(栈): {preorder_iterative(root)}")   # [1,2,4,5,3,6]
    print(f"  中序(栈): {inorder_iterative(root)}")    # [4,2,5,1,3,6]
    print(f"  后序(栈): {postorder_iterative(root)}")  # [4,5,2,6,3,1]


# =============================================================================
# 扩展 3：拓扑排序（Kahn 算法 + DFS 算法）
# =============================================================================
def topo_sort_kahn(graph, num_nodes):
    """Kahn 算法（BFS）：不断移除入度为 0 的节点"""
    in_degree = [0] * num_nodes
    for u in graph:
        for v in graph[u]:
            in_degree[v] += 1

    queue = deque([i for i in range(num_nodes) if in_degree[i] == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != num_nodes:
        return None  # 有环
    return result


def topo_sort_dfs(graph, num_nodes):
    """DFS 算法：后序逆序"""
    visited = [False] * num_nodes
    result = []

    def _dfs(node):
        visited[node] = True
        for neighbor in graph[node]:
            if not visited[neighbor]:
                _dfs(neighbor)
        result.append(node)  # 后序加入

    for i in range(num_nodes):
        if not visited[i]:
            _dfs(i)

    return list(reversed(result))  # 逆序 = 拓扑序


def test_topo():
    print("\n=== 扩展3: 拓扑排序 ===")
    # 课程依赖: 0→1, 0→2, 1→3, 2→3, 3→4
    graph = defaultdict(list)
    graph[0] = [1, 2]
    graph[1] = [3]
    graph[2] = [3]
    graph[3] = [4]
    graph[4] = []

    kahn = topo_sort_kahn(graph, 5)
    dfs = topo_sort_dfs(graph, 5)
    print(f"  Kahn(BFS): {kahn}")
    print(f"  DFS逆序:   {dfs}")

    # 测试有环情况
    cyclic = defaultdict(list)
    cyclic[0] = [1]; cyclic[1] = [2]; cyclic[2] = [0]
    result = topo_sort_kahn(cyclic, 3)
    print(f"  有环图排序: {result} (None=检测到环)")


# =============================================================================
# 扩展 4：优先队列 + 合并 K 个有序链表 (LeetCode 23)
# =============================================================================
def merge_k_sorted_lists(lists):
    """用最小堆合并 K 个有序链表"""
    # 用虚拟头节点简化
    dummy = DoublyListNode(0)
    cur = dummy
    heap = []

    # 每个链表的第一个元素入堆
    for i, head in enumerate(lists):
        if head:
            heapq.heappush(heap, (head.val, i, head))

    while heap:
        val, i, node = heapq.heappop(heap)
        cur.next = node; node.prev = cur; cur = cur.next
        if node.next:
            heapq.heappush(heap, (node.next.val, i, node.next))

    if dummy.next:
        dummy.next.prev = None
    return dummy.next


def merge_k_sorted_arrays(arrays):
    """合并 K 个有序数组（简化版，直接用堆）"""
    heap = []
    for i, arr in enumerate(arrays):
        if arr:
            heapq.heappush(heap, (arr[0], i, 0))

    result = []
    while heap:
        val, arr_idx, elem_idx = heapq.heappop(heap)
        result.append(val)
        if elem_idx + 1 < len(arrays[arr_idx]):
            next_val = arrays[arr_idx][elem_idx + 1]
            heapq.heappush(heap, (next_val, arr_idx, elem_idx + 1))

    return result


def test_merge_k():
    print("\n=== 扩展4: 合并K个有序链表/数组 ===")
    # 合并 K 个有序数组
    arrays = [
        [1, 4, 7],
        [2, 5, 8],
        [3, 6, 9, 10],
    ]
    merged = merge_k_sorted_arrays(arrays)
    print(f"  合并3个有序数组: {merged}")

    # 合并 K 个有序链表
    lists = []
    for arr in arrays:
        dl = DoublyLinkedList()
        for v in arr: dl.append(v)
        lists.append(dl.head)

    merged_head = merge_k_sorted_lists(lists)
    result = []
    cur = merged_head
    while cur: result.append(cur.val); cur = cur.next
    print(f"  合并3个有序链表: {result}")

    # 性能对比：堆 vs 朴素合并
    import time
    import random
    big_arrays = [sorted(random.randint(0, 100000) for _ in range(1000)) for _ in range(50)]

    start = time.time()
    heap_result = merge_k_sorted_arrays(big_arrays)
    heap_time = time.time() - start

    start = time.time()
    naive = []
    for arr in big_arrays: naive.extend(arr)
    naive.sort()
    naive_time = time.time() - start

    print(f"  50×1000元素: 堆合并 {heap_time:.4f}s vs sort {naive_time:.4f}s")
    print(f"  结果正确: {heap_result == naive}")


# =============================================================================
# 扩展 5：并查集（Union-Find）
# =============================================================================
class UnionFind:
    """并查集：近 O(1) 的合并和查找（路径压缩 + 按秩合并）"""

    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.count = n  # 连通分量数

    def find(self, x):
        """路径压缩：查找根节点"""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # 压缩路径
        return self.parent[x]

    def union(self, x, y):
        """按秩合并：矮树挂到高树下"""
        px, py = self.find(x), self.find(y)
        if px == py:
            return False  # 已在同一集合
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        self.count -= 1
        return True

    def connected(self, x, y):
        return self.find(x) == self.find(y)


def test_union_find():
    print("\n=== 扩展5: 并查集 ===")
    # 场景：社交网络连通性
    # 0-1, 1-2, 3-4 → 两组: {0,1,2} {3,4}
    uf = UnionFind(5)
    uf.union(0, 1)
    uf.union(1, 2)
    uf.union(3, 4)

    print(f"  连通分量数: {uf.count}")  # 2
    print(f"  0和2连通: {uf.connected(0, 2)}")  # True
    print(f"  0和3连通: {uf.connected(0, 3)}")  # False

    uf.union(2, 3)  # 连接两组
    print(f"  合并后连通分量数: {uf.count}")  # 1
    print(f"  0和4连通: {uf.connected(0, 4)}")  # True

    # LeetCode 200 岛屿数量（简化版）
    grid = [
        [1, 1, 0, 0, 0],
        [1, 1, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 0, 1, 1],
    ]
    rows, cols = len(grid), len(grid[0])
    uf2 = UnionFind(rows * cols)
    water = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 0:
                water += 1
                continue
            if r + 1 < rows and grid[r+1][c] == 1:
                uf2.union(r * cols + c, (r+1) * cols + c)
            if c + 1 < cols and grid[r][c+1] == 1:
                uf2.union(r * cols + c, r * cols + c + 1)
    islands = uf2.count - water
    print(f"  岛屿数量(LeetCode 200): {islands}")  # 3


# =============================================================================
# 扩展 6：加权图 + Dijkstra 最短路径
# =============================================================================
class WeightedGraph:
    """加权图（邻接表）"""

    def __init__(self):
        self.adj = defaultdict(list)  # {node: [(neighbor, weight)]}

    def add_edge(self, u, v, weight, directed=False):
        self.adj[u].append((v, weight))
        if not directed:
            self.adj[v].append((u, weight))

    def dijkstra(self, start):
        """Dijkstra 算法：单源最短路径（非负权重）"""
        dist = {start: 0}
        heap = [(0, start)]
        visited = set()

        while heap:
            d, node = heapq.heappop(heap)
            if node in visited:
                continue
            visited.add(node)
            for neighbor, weight in self.adj[node]:
                new_dist = d + weight
                if neighbor not in dist or new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    heapq.heappush(heap, (new_dist, neighbor))

        return dist

    def dijkstra_with_path(self, start, end):
        """Dijkstra 带路径回溯"""
        dist = {start: 0}
        parent = {}
        heap = [(0, start)]
        visited = set()

        while heap:
            d, node = heapq.heappop(heap)
            if node in visited:
                continue
            visited.add(node)
            if node == end:
                # 回溯路径
                path = [end]
                cur = end
                while cur in parent:
                    cur = parent[cur]
                    path.append(cur)
                return list(reversed(path)), d
            for neighbor, weight in self.adj[node]:
                new_dist = d + weight
                if neighbor not in dist or new_dist < dist[neighbor]:
                    dist[neighbor] = new_dist
                    parent[neighbor] = node
                    heapq.heappush(heap, (new_dist, neighbor))

        return None, float('inf')


def test_dijkstra():
    print("\n=== 扩展6: Dijkstra最短路径 ===")
    wg = WeightedGraph()
    # 加权图:
    #     A --4-- B --1-- C
    #     |       |       |
    #     2       5       3
    #     |       |       |
    #     D --8-- E --2-- F
    edges = [("A","B",4),("B","C",1),("A","D",2),("B","E",5),
             ("C","F",3),("D","E",8),("E","F",2)]
    for u, v, w in edges:
        wg.add_edge(u, v, w)

    # 从 A 出发的最短距离
    dist = wg.dijkstra("A")
    print(f"  从A出发的最短距离: {dist}")

    # A 到 F 的最短路径
    path, distance = wg.dijkstra_with_path("A", "F")
    print(f"  A→F最短路径: {' → '.join(path)}, 总距离: {distance}")

    # 对比 BFS 最短路径（跳数）vs Dijkstra（权重）
    print(f"  (BFS最短跳数路径是 A→B→C→F, 但加权最短是 A→D→E→F)")


# =============================================================================
# 主函数
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🔧 数据结构扩展练习")
    print("=" * 60)

    test_doubly()
    test_tree_iterative()
    test_topo()
    test_merge_k()
    test_union_find()
    test_dijkstra()

    print("\n" + "=" * 60)
    print("✅ 数据结构全部掌握，核心知识点：")
    print("=" * 60)
    print("""
1. 链表：单链表/双向链表，O(1)插入删除，O(n)查找，反转链表三指针法
2. 二叉树：BST性质（左<根<右），中序=有序，递归/非递归遍历（栈模拟）
3. 图：邻接表表示，BFS(队列)找最短路径，DFS(递归/栈)遍历，拓扑排序(Kahn/DFS)
4. LRU缓存：OrderedDict，move_to_end标记最近使用，popitem(last=False)淘汰最久
5. 优先队列：heapq最小堆，O(log n)插入弹出，合并K个有序序列
6. 并查集：路径压缩+按秩合并，近O(1)合并查找，连通分量/岛屿数量
7. Dijkstra：最小堆优化的单源最短路径，适合非负权重图
8. 复杂度对比：BFS最短跳数 vs Dijkstra最短权重，选对算法很重要
""")
