// 静态 mock 数据：Workspace 页面
// 资源层级对齐当前后端模型：
//   source_workspace（真源项目代码） -> session_workspace（基于真源派生的分支）
// 其中：
//   - source_workspace.files 是最终真源项目代码本身
//   - source_workspace.session_workspaces 是基于这份真源新建的派生工作区
// 每个节点都带唯一 id，用于选中与详情索引（避免真源与派生分支中同名路径冲突）。
// 后续接入 gateway_service 的 workspace_page 聚合接口时只需替换数据来源。

export const sourceWorkspaces = [
  {
    source_workspace_id: 'src-ecommerce',
    name: 'ecommerce-platform',
    root_path: '/repos/ecommerce-platform',
    status: 'ready',
    created_at: '2026-06-01T10:00:00Z',
    // 真源项目代码（最终代码真源，所有 session workspace 都基于这份代码派生）
    files: [
      {
        id: 'src-ecommerce:src',
        type: 'directory',
        name: 'src',
        path: 'src',
        children: [
          { id: 'src-ecommerce:src/checkout.py', type: 'file', name: 'checkout.py', path: 'src/checkout.py' },
          { id: 'src-ecommerce:src/coupon.py', type: 'file', name: 'coupon.py', path: 'src/coupon.py' },
          { id: 'src-ecommerce:src/payment_callback.py', type: 'file', name: 'payment_callback.py', path: 'src/payment_callback.py' },
          { id: 'src-ecommerce:src/order.py', type: 'file', name: 'order.py', path: 'src/order.py' },
        ],
      },
      {
        id: 'src-ecommerce:tests',
        type: 'directory',
        name: 'tests',
        path: 'tests',
        children: [
          { id: 'src-ecommerce:tests/test_checkout.py', type: 'file', name: 'test_checkout.py', path: 'tests/test_checkout.py' },
        ],
      },
      { id: 'src-ecommerce:README.md', type: 'file', name: 'README.md', path: 'README.md' },
      { id: 'src-ecommerce:pyproject.toml', type: 'file', name: 'pyproject.toml', path: 'pyproject.toml' },
    ],
    session_workspaces: [
      {
        session_workspace_id: 'sw-electron-checkout',
        name: 'checkout-refactor',
        root_path: '/sandbox/checkout-refactor',
        status: 'ready',
        files: [
          {
            id: 'sw-electron-checkout:src',
            type: 'directory',
            name: 'src',
            path: 'src',
            children: [
              { id: 'sw-electron-checkout:src/checkout.py', type: 'file', name: 'checkout.py', path: 'src/checkout.py' },
              { id: 'sw-electron-checkout:src/coupon.py', type: 'file', name: 'coupon.py', path: 'src/coupon.py' },
              { id: 'sw-electron-checkout:src/payment_callback.py', type: 'file', name: 'payment_callback.py', path: 'src/payment_callback.py' },
            ],
          },
          { id: 'sw-electron-checkout:README.md', type: 'file', name: 'README.md', path: 'README.md' },
        ],
      },
      {
        session_workspace_id: 'sw-order-api',
        name: 'order-api',
        root_path: '/sandbox/order-api',
        status: 'ready',
        files: [
          {
            id: 'sw-order-api:app',
            type: 'directory',
            name: 'app',
            path: 'app',
            children: [
              { id: 'sw-order-api:app/routes.py', type: 'file', name: 'routes.py', path: 'app/routes.py' },
              { id: 'sw-order-api:app/models.py', type: 'file', name: 'models.py', path: 'app/models.py' },
            ],
          },
        ],
      },
    ],
  },
  {
    source_workspace_id: 'src-website',
    name: 'marketing-website',
    root_path: '/repos/marketing-website',
    status: 'ready',
    created_at: '2026-05-20T09:00:00Z',
    files: [
      {
        id: 'src-website:components',
        type: 'directory',
        name: 'components',
        path: 'components',
        children: [
          { id: 'src-website:components/Hero.jsx', type: 'file', name: 'Hero.jsx', path: 'components/Hero.jsx' },
          { id: 'src-website:components/Hero.css', type: 'file', name: 'Hero.css', path: 'components/Hero.css' },
          { id: 'src-website:components/Footer.jsx', type: 'file', name: 'Footer.jsx', path: 'components/Footer.jsx' },
        ],
      },
      { id: 'src-website:index.html', type: 'file', name: 'index.html', path: 'index.html' },
      { id: 'src-website:package.json', type: 'file', name: 'package.json', path: 'package.json' },
    ],
    session_workspaces: [
      {
        session_workspace_id: 'sw-landing-redesign',
        name: 'landing-redesign',
        root_path: '/sandbox/landing-redesign',
        status: 'ready',
        files: [
          {
            id: 'sw-landing-redesign:components',
            type: 'directory',
            name: 'components',
            path: 'components',
            children: [
              { id: 'sw-landing-redesign:components/Hero.jsx', type: 'file', name: 'Hero.jsx', path: 'components/Hero.jsx' },
              { id: 'sw-landing-redesign:components/Hero.css', type: 'file', name: 'Hero.css', path: 'components/Hero.css' },
            ],
          },
          { id: 'sw-landing-redesign:index.html', type: 'file', name: 'index.html', path: 'index.html' },
        ],
      },
      {
        session_workspace_id: 'sw-membership-spec',
        name: 'membership-spec',
        root_path: '/sandbox/membership-spec',
        status: 'ready',
        files: [
          { id: 'sw-membership-spec:spec.md', type: 'file', name: 'spec.md', path: 'spec.md' },
        ],
      },
    ],
  },
];

// 右侧详情区占位数据，以资源 id 为键。
// 资源类型：source_workspace / session_workspace / file
export const resourceDetails = {
  'src-ecommerce': {
    kind: 'source_workspace',
    title: 'ecommerce-platform',
    type_label: 'Source Workspace',
    path: '/repos/ecommerce-platform',
    description: '电商平台真源项目代码，承载结算、订单等子系统。所有 session workspace 都基于这份代码派生。',
    bindings: ['真源项目代码', '2 个派生 session workspace', '状态 ready'],
    preview_kind: 'note',
    preview: '这是项目真源（source workspace），即最终项目代码本身。Agent 不直接写回真源，改动会先在派生的 session workspace 中以 Proposal 形式产生，确认后再合并回真源。',
  },
  'src-ecommerce:src/checkout.py': {
    kind: 'file',
    title: 'checkout.py',
    type_label: 'File · 真源',
    path: 'src/checkout.py',
    description: '真源中的结算主流程：价格计算、优惠券校验、支付回调编排。',
    bindings: ['source workspace ecommerce-platform'],
    preview_kind: 'code',
    preview: `def calculate_total(cart, coupon=None):
    subtotal = sum(item.price * item.qty for item in cart.items)
    discount = coupon.apply(subtotal) if coupon else 0
    return subtotal - discount


def settle(order):
    total = calculate_total(order.cart, order.coupon)
    return create_payment(order.id, total)
`,
  },
  'src-ecommerce:README.md': {
    kind: 'file',
    title: 'README.md',
    type_label: 'File · 真源',
    path: 'README.md',
    description: '真源项目说明文档。',
    bindings: ['source workspace ecommerce-platform'],
    preview_kind: 'note',
    preview: '# ecommerce-platform\n\n电商平台真源项目代码。本阶段为静态占位，文件内容暂不接入真实读取。',
  },
  'sw-electron-checkout': {
    kind: 'session_workspace',
    title: 'checkout-refactor',
    type_label: 'Session Workspace',
    path: '/sandbox/checkout-refactor',
    description: '结算模块重构的隔离工作区，基于 ecommerce-platform 真源派生。',
    bindings: ['派生自 ecommerce-platform', '绑定 session 电商后台重构'],
    preview_kind: 'note',
    preview: '该 session workspace 由真源 source workspace 派生，用于承载本轮改动的 sandbox 与 Proposal，确认后再合并回真源。',
  },
  'sw-electron-checkout:src/checkout.py': {
    kind: 'file',
    title: 'checkout.py',
    type_label: 'File · 派生',
    path: 'src/checkout.py',
    description: '派生工作区中的结算主流程，包含本轮幂等性改动。',
    bindings: ['session workspace checkout-refactor', '派生自 ecommerce-platform'],
    preview_kind: 'code',
    preview: `def settle(order):
    # 本轮新增：支付回调幂等键
    idempotency_key = build_idempotency_key(order.id)
    total = calculate_total(order.cart, order.coupon)
    return create_payment(order.id, total, idempotency_key)
`,
  },
};
