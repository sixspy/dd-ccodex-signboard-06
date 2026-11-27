window.SB_VIEWS = window.SB_VIEWS || {};
window.SB_VIEWS["screens-view"] = {
  template: `
  <div class="panel">
    <h2>屏幕台账</h2>
    <p class="lead">物理终端绑定分区、分辨率与在线状态；标注当前生效的单屏覆盖及到期。</p>
    <div class="row-form">
      <button class="ghost" @click="reload">刷新</button>
    </div>
    <table>
      <thead><tr><th>编码</th><th>标题</th><th>分区</th><th>分辨率</th><th>状态</th><th>风险</th><th>生效覆盖</th></tr></thead>
      <tbody>
        <tr v-for="s in items" :key="s.id">
          <td>{{ s.code }}</td><td>{{ s.title }}</td><td>{{ s.zone_title }}</td>
          <td>{{ s.resolution }}</td>
          <td><span class="badge" :class="s.status==='online'?'':(s.status==='maintenance'?'bad':'warn')">{{ s.status_label }}</span></td>
          <td>{{ s.risk_level }}</td>
          <td>
            <span v-if="s.active_override" class="badge" :class="s.active_override.effect==='force_blank' ? 'warn' : ''">
              {{ s.active_override.effect_label }}<template v-if="s.active_override.expires_label">（至 {{ s.active_override.expires_label }}）</template>
            </span>
            <span v-else>—</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>`,
  data() { return { items: [] }; },
  async mounted() { await this.reload(); },
  methods: {
    async reload() { this.items = (await SB.api("/api/screens")).items; }
  }
};
