// RTK Query：所有读写走同源 /api（开发期 Vite 代理到 gateway）。
// 缓存 + 后台 refetch（stale-while-revalidate）由 RTK Query 内置提供。
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  tagTypes: ['Session', 'SourceWorkspace'],
  // 重新挂载或入参变化时后台刷新；旧数据在 refetch 期间保持可见。
  refetchOnMountOrArgChange: true,
  endpoints: (builder) => ({
    // ---- 读 ----
    listSessions: builder.query({
      query: () => '/sessions',
      providesTags: [{ type: 'Session', id: 'LIST' }],
    }),
    getSessionPage: builder.query({
      query: (sessionId) => `/session-page/${sessionId}`,
    }),
    listSourceWorkspaces: builder.query({
      query: () => '/source-workspaces',
      providesTags: [{ type: 'SourceWorkspace', id: 'LIST' }],
    }),
    getWorkspacePage: builder.query({
      query: (sourceWorkspaceId) => `/workspace-page/${sourceWorkspaceId}`,
    }),
    getWorkspaceTree: builder.query({
      query: ({ sourceId, path = '.' }) => {
        const search = new URLSearchParams({ path }).toString();
        return `/source-workspaces/${sourceId}/tree?${search}`;
      },
    }),

    // ---- 写 ----
    postSessionMessage: builder.mutation({
      query: ({ sessionId, content }) => ({
        url: `/sessions/${sessionId}/messages`,
        method: 'POST',
        body: { content },
      }),
    }),
    createSessionFromSource: builder.mutation({
      query: ({ source_workspace_id, title }) => ({
        url: '/sessions/from-source',
        method: 'POST',
        body: { source_workspace_id, title },
      }),
      invalidatesTags: [{ type: 'Session', id: 'LIST' }],
    }),
    createSourceWorkspace: builder.mutation({
      query: ({ name, root_path }) => ({
        url: '/source-workspaces',
        method: 'POST',
        body: { name, root_path },
      }),
      invalidatesTags: [{ type: 'SourceWorkspace', id: 'LIST' }],
    }),
  }),
});

export const {
  useListSessionsQuery,
  useGetSessionPageQuery,
  useListSourceWorkspacesQuery,
  useGetWorkspacePageQuery,
  useLazyGetWorkspaceTreeQuery,
  usePostSessionMessageMutation,
  useCreateSessionFromSourceMutation,
  useCreateSourceWorkspaceMutation,
} = api;
