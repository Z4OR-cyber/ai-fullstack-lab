/*
 * Q13: 链表实战
 * 知识点: 单链表/双向链表/循环链表、内存池
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ===== 单链表 ===== */
typedef struct slist_node {
    int data;
    struct slist_node *next;
} slist_node;

typedef struct {
    slist_node *head;
    int size;
} slist;

static slist *slist_create(void)
{
    slist *l = malloc(sizeof(slist));
    if (l) { l->head = NULL; l->size = 0; }
    return l;
}

static void slist_push_front(slist *l, int data)
{
    slist_node *node = malloc(sizeof(slist_node));
    if (!node) return;
    node->data = data;
    node->next = l->head;
    l->head = node;
    l->size++;
}

static void slist_push_back(slist *l, int data)
{
    slist_node *node = malloc(sizeof(slist_node));
    if (!node) return;
    node->data = data;
    node->next = NULL;
    if (!l->head) {
        l->head = node;
    } else {
        slist_node *p = l->head;
        while (p->next) p = p->next;
        p->next = node;
    }
    l->size++;
}

static void slist_print(const slist *l, const char *label)
{
    printf("  %s [%d]: ", label, l->size);
    slist_node *p = l->head;
    while (p) {
        printf("%d -> ", p->data);
        p = p->next;
    }
    printf("NULL\n");
}

static void slist_free(slist *l)
{
    slist_node *p = l->head;
    while (p) {
        slist_node *next = p->next;
        free(p);
        p = next;
    }
    free(l);
}

/* 反转单链表 */
static void slist_reverse(slist *l)
{
    slist_node *prev = NULL, *cur = l->head, *next;
    while (cur) {
        next = cur->next;
        cur->next = prev;
        prev = cur;
        cur = next;
    }
    l->head = prev;
}

/* ===== 双向链表 ===== */
typedef struct dlist_node {
    int data;
    struct dlist_node *prev;
    struct dlist_node *next;
} dlist_node;

typedef struct {
    dlist_node *head;
    dlist_node *tail;
    int size;
} dlist;

static dlist *dlist_create(void)
{
    dlist *l = malloc(sizeof(dlist));
    if (l) { l->head = l->tail = NULL; l->size = 0; }
    return l;
}

static void dlist_push_back(dlist *l, int data)
{
    dlist_node *node = malloc(sizeof(dlist_node));
    if (!node) return;
    node->data = data;
    node->next = NULL;
    node->prev = l->tail;
    if (l->tail)
        l->tail->next = node;
    else
        l->head = node;
    l->tail = node;
    l->size++;
}

static void dlist_print_forward(const dlist *l)
{
    printf("  双向链表正向 [%d]: ", l->size);
    dlist_node *p = l->head;
    while (p) {
        printf("%d ", p->data);
        p = p->next;
    }
    printf("\n");
}

static void dlist_print_backward(const dlist *l)
{
    printf("  双向链表反向 [%d]: ", l->size);
    dlist_node *p = l->tail;
    while (p) {
        printf("%d ", p->data);
        p = p->prev;
    }
    printf("\n");
}

static void dlist_free(dlist *l)
{
    dlist_node *p = l->head;
    while (p) {
        dlist_node *next = p->next;
        free(p);
        p = next;
    }
    free(l);
}

/* ===== 循环链表 (约瑟夫环) ===== */
static int josephus(int n, int k)
{
    /* 创建循环链表 */
    slist_node *head = malloc(sizeof(slist_node));
    head->data = 1;
    slist_node *prev = head;
    for (int i = 2; i <= n; i++) {
        slist_node *node = malloc(sizeof(slist_node));
        node->data = i;
        prev->next = node;
        prev = node;
    }
    prev->next = head;  /* 成环 */

    /* 约瑟夫环: 每数到k淘汰 */
    slist_node *cur = head;
    slist_node *pre = prev;
    int remaining = n;
    while (remaining > 1) {
        for (int i = 1; i < k; i++) {
            pre = cur;
            cur = cur->next;
        }
        pre->next = cur->next;
        slist_node *tmp = cur;
        cur = cur->next;
        free(tmp);
        remaining--;
    }
    int survivor = cur->data;
    free(cur);
    return survivor;
}

/* ===== 简易内存池 ===== */
#define POOL_SIZE 64

typedef struct pool_node {
    slist_node data;       /* 复用单链表节点 */
    int in_use;
    struct pool_node *next;
} pool_node;

typedef struct {
    pool_node nodes[POOL_SIZE];
    pool_node *free_list;
} mem_pool;

static void pool_init(mem_pool *p)
{
    p->free_list = NULL;
    for (int i = POOL_SIZE - 1; i >= 0; i--) {
        p->nodes[i].in_use = 0;
        p->nodes[i].next = p->free_list;
        p->free_list = &p->nodes[i];
    }
}

static slist_node *pool_alloc(mem_pool *p)
{
    if (!p->free_list) return NULL;
    pool_node *pn = p->free_list;
    p->free_list = pn->next;
    pn->in_use = 1;
    return &pn->data;
}

static void pool_free(mem_pool *p, slist_node *node)
{
    pool_node *pn = (pool_node *)node;
    pn->in_use = 0;
    pn->next = p->free_list;
    p->free_list = pn;
}

int main(void)
{
    printf("========================================\n");
    printf("  Q13: 链表实战\n");
    printf("========================================\n\n");

    /* 1. 单链表 */
    printf("--- 1. 单链表 ---\n");
    slist *sl = slist_create();
    slist_push_back(sl, 10);
    slist_push_back(sl, 20);
    slist_push_back(sl, 30);
    slist_push_front(sl, 5);
    slist_push_front(sl, 1);
    slist_print(sl, "原始");

    slist_reverse(sl);
    slist_print(sl, "反转");

    slist_reverse(sl);
    slist_print(sl, "再反转");
    slist_free(sl);
    printf("\n");

    /* 2. 双向链表 */
    printf("--- 2. 双向链表 ---\n");
    dlist *dl = dlist_create();
    for (int i = 1; i <= 6; i++)
        dlist_push_back(dl, i * 10);
    dlist_print_forward(dl);
    dlist_print_backward(dl);
    dlist_free(dl);
    printf("\n");

    /* 3. 循环链表 — 约瑟夫环 */
    printf("--- 3. 循环链表 — 约瑟夫环 ---\n");
    printf("  n=5, k=2 -> 幸存者: %d\n", josephus(5, 2));
    printf("  n=5, k=3 -> 幸存者: %d\n", josephus(5, 3));
    printf("  n=10, k=3 -> 幸存者: %d\n", josephus(10, 3));
    printf("  n=41, k=3 -> 幸存者: %d (经典约瑟夫问题)\n\n", josephus(41, 3));

    /* 4. 内存池 */
    printf("--- 4. 简易内存池 ---\n");
    mem_pool pool;
    pool_init(&pool);
    printf("  池大小: %d 节点\n", POOL_SIZE);

    slist_node *nodes[5];
    for (int i = 0; i < 5; i++) {
        nodes[i] = pool_alloc(&pool);
        if (nodes[i]) nodes[i]->data = i * 100;
    }
    printf("  分配5个节点: ");
    for (int i = 0; i < 5; i++)
        printf("%d ", nodes[i]->data);
    printf("\n");

    /* 释放2个 */
    pool_free(&pool, nodes[1]);
    pool_free(&pool, nodes[3]);
    printf("  释放节点1和3\n");

    /* 再分配2个 */
    slist_node *n1 = pool_alloc(&pool);
    slist_node *n2 = pool_alloc(&pool);
    n1->data = 999;
    n2->data = 888;
    printf("  再分配2个: %d, %d (复用已释放的)\n", n1->data, n2->data);
    printf("  优点: 无系统调用开销, 无碎片, 适合高频分配释放\n");

    printf("\n✅ Q13 通过\n");
    return 0;
}
