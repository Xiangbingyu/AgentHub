/**
 * 动态模块加载器
 * 根据任务类型动态加载相关模块
 */

const fs = require('fs');
const path = require('path');

const MODULES_DIR = path.join(__dirname, 'modules');

/**
 * 任务类型到模块的映射
 */
const TASK_MODULE_MAP = {
  // 开发新功能
  '开发': ['guide', 'naming', 'code-style', 'react', 'components', 'api', 'commands'],
  '新增': ['guide', 'naming', 'code-style', 'react', 'components', 'api', 'commands'],
  '功能': ['guide', 'naming', 'code-style', 'react', 'components', 'api', 'commands'],
  
  // 重构
  '重构': ['refactor', 'guide', 'code-style'],
  'refactor': ['refactor', 'guide', 'code-style'],
  
  // Bug修复
  '修复': ['guide', 'code-style', 'react', 'quality'],
  'bug': ['guide', 'code-style', 'react', 'quality'],
  'fix': ['guide', 'code-style', 'react', 'quality'],
  
  // 了解项目
  '了解': ['tech-stack', 'directory', 'naming'],
  '结构': ['tech-stack', 'directory', 'naming'],
  
  // 状态管理
  'redux': ['redux'],
  '状态': ['redux'],
  
  // 组件开发
  '组件': ['react', 'components', 'css', 'naming'],
  'component': ['react', 'components', 'css', 'naming'],
  
  // API开发
  'api': ['api', 'commands'],
  '接口': ['api', 'commands'],
  
  // 代码审查
  'review': ['code-style', 'react', 'quality', 'convention'],
  '审查': ['code-style', 'react', 'quality', 'convention'],
  
  // 默认加载
  'default': ['guide', 'naming', 'code-style', 'react', 'components'],
};

/**
 * 根据任务关键词获取需要加载的模块
 * @param {string} task 任务描述
 * @returns {string[]} 模块名称数组
 */
function getModulesForTask(task) {
  const taskLower = task.toLowerCase();
  
  for (const [keyword, modules] of Object.entries(TASK_MODULE_MAP)) {
    if (taskLower.includes(keyword.toLowerCase())) {
      return modules;
    }
  }
  
  return TASK_MODULE_MAP['default'];
}

/**
 * 加载指定模块的内容
 * @param {string[]} moduleNames 模块名称数组
 * @returns {string} 合并后的模块内容
 */
function loadModules(moduleNames) {
  const contents = [];
  
  for (const moduleName of moduleNames) {
    const modulePath = path.join(MODULES_DIR, `${moduleName}.md`);
    
    if (fs.existsSync(modulePath)) {
      const content = fs.readFileSync(modulePath, 'utf8');
      contents.push(`\n## ${moduleName.toUpperCase()}\n`);
      contents.push(content);
    }
  }
  
  return contents.join('\n');
}

/**
 * 根据任务动态加载模块内容
 * @param {string} task 任务描述
 * @returns {string} 动态加载的内容
 */
function dynamicLoad(task) {
  const modules = getModulesForTask(task);
  const content = loadModules(modules);
  
  return content;
}

module.exports = {
  getModulesForTask,
  loadModules,
  dynamicLoad,
};
