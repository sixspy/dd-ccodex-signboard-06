window.SB_VIEWS = window.SB_VIEWS || {};
window.SB_VIEWS["history-view"] = {
  template: `
  <div class="panel">
    <h2>变更历史</h2>
    <p class="lead">发布、撤屏、覆盖与台账变更同源可追溯；单屏覆盖记录含到期时刻。</p>
    <div class="row-form">
      <select v-model="kind" @change="reload">
        <option value="">全部实体</option>
        <option value="override">单屏覆盖</option>
        <option value="panic">紧急撤屏</option>
        <option value="publication">发布上屏</option>
      </select>
      <button class="ghost" @click="reload">刷新</button>
    </div>
    <table>
      <thead><tr><th>ID</th><th>实体</th><th>动作</th><th>详情</th><th>到期</th><th>操作者</th></tr></thead>
      <tbody>
        <tr v-for="h in items" :key="h.id">
          <td>{{ h.id }}</td><td>{{ h.entity_kind }}#{{ h.entity_id }}</td>
          <td>{{ h.action }}</td>
          <td>{{ h.detail }}</td>
          <td>
            <span v-if="h.override_expires_at" class="badge">{{ fmt(h.override_expires_at) }}</span>
            <span v-else>—</span>
          </td>
          <td>{{ h.actor }}</td>
        </tr>
      </tbody>
    </table>
  </div>`,
  data() { return { items: [], kind: "" }; },
  async mounted() { await this.reload(); },
  methods: {
    async reload() {
      const q = this.kind ? ("?entity_kind=" + encodeURIComponent(this.kind)) : "";
      this.items = (await SB.api("/api/history" + q)).items;
    },
    fmt(ts) {
      const d = new Date(ts * 1000);
      const p = n => String(n).padStart(2, "0");
      return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
    }
  }
};
