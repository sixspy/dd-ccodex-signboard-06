window.SB_VIEWS = window.SB_VIEWS || {};
window.SB_VIEWS["overrides-view"] = {
  template: `
  <div>
    <div class="panel">
      <h2>单屏覆盖</h2>
      <p class="lead">临时强制清单 / 空屏 / 单素材，求值优先于正式发布。强制空屏须填失效时刻；缺失效时刻只落影子草案，正式覆盖册零增。</p>
      <div class="row-form">
        <input v-model.number="form.screen_id" type="number" placeholder="屏幕ID" />
        <select v-model="form.effect">
          <option value="force_blank">强制空屏</option>
          <option value="force_playlist">强制清单</option>
          <option value="force_asset">强制单素材</option>
        </select>
        <input v-model.number="form.playlist_id" type="number" placeholder="清单ID(可选)" />
        <input v-model.number="form.asset_id" type="number" placeholder="素材ID(可选)" />
        <input v-model="form.expires_at" type="datetime-local" placeholder="失效时刻" />
        <input v-model="form.note" placeholder="备注" />
      </div>
      <div class="row-form">
        <button class="primary" @click="create">正式覆盖（甲）</button>
        <button class="ghost" @click="createShadow">写影子草案（乙）</button>
      </div>
      <p class="err" v-if="error">{{ error }}</p>
      <p v-if="msg">{{ msg }}</p>
    </div>
    <div class="two-col">
      <div class="panel">
        <h3>正式覆盖</h3>
        <table>
          <thead><tr><th>ID</th><th>屏幕</th><th>效果</th><th>生效</th><th>到期</th><th>备注</th></tr></thead>
          <tbody>
            <tr v-for="o in items" :key="o.id">
              <td>{{ o.id }}</td><td>{{ o.screen_code }}</td><td>{{ o.effect_label }}</td>
              <td>{{ o.active ? "是" : "否" }}</td>
              <td><span class="badge" :class="o.expired ? 'bad' : ''">{{ o.expires_label || "—" }}</span></td>
              <td>{{ o.note || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="panel">
        <h3>影子草案</h3>
        <table>
          <thead><tr><th>ID</th><th>屏幕</th><th>效果</th><th>状态</th><th>到期</th><th>备注</th></tr></thead>
          <tbody>
            <tr v-for="s in shadows" :key="s.id">
              <td>{{ s.id }}</td><td>{{ s.screen_id }}</td><td>{{ s.effect_label }}</td>
              <td>{{ s.status }}</td><td>{{ s.expires_label || "—" }}</td><td>{{ s.note || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>`,
  data() {
    return {
      items: [], shadows: [], error: "", msg: "",
      form: { screen_id: 1, effect: "force_blank", playlist_id: null, asset_id: null, expires_at: "", note: "" }
    };
  },
  async mounted() { await this.reload(); },
  methods: {
    _body() {
      const body = { ...this.form };
      if (!body.expires_at) body.expires_at = null;
      if (body.effect === "force_blank") { body.playlist_id = null; body.asset_id = null; }
      return body;
    },
    async reload() {
      this.items = (await SB.api("/api/overrides")).items;
      this.shadows = (await SB.api("/api/overrides/shadows")).items;
    },
    async create() {
      this.error = ""; this.msg = "";
      try {
        const r = await SB.api("/api/overrides/official", { method: "POST", body: JSON.stringify(this._body()) });
        this.msg = r.path === "shadow"
          ? "缺失效时刻，已转影子草案 id=" + r.id + "（正式覆盖册零增）"
          : "正式覆盖完成 id=" + r.id;
        await this.reload();
      } catch (e) { this.error = e.message; }
    },
    async createShadow() {
      this.error = ""; this.msg = "";
      try {
        const r = await SB.api("/api/overrides/shadow", { method: "POST", body: JSON.stringify(this._body()) });
        this.msg = "影子草案已写 id=" + r.id;
        await this.reload();
      } catch (e) { this.error = e.message; }
    }
  }
};
