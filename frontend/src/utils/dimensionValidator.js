export function validateDimensions(dimensions) {
  const errors = []

  for (const dim of dimensions) {
    if (!dim.name?.trim()) {
      errors.push({
        field: 'name',
        message: '请填写所有维度名称',
        dimension: dim.name || '未命名维度'
      })
    }

    if (!dim.full_score || dim.full_score <= 0) {
      errors.push({
        field: 'full_score',
        message: `${dim.name || '未命名维度'} 的满分必须大于0`,
        dimension: dim.name || '未命名维度'
      })
    }

    if (dim.highest_score !== null && dim.highest_score > dim.full_score) {
      errors.push({
        field: 'highest_score',
        message: `${dim.name} 的最高分不能超过满分`,
        dimension: dim.name
      })
    }

    if (dim.lowest_score !== null && dim.lowest_score > dim.full_score) {
      errors.push({
        field: 'lowest_score',
        message: `${dim.name} 的最低分不能超过满分`,
        dimension: dim.name
      })
    }

    if (dim.highest_score !== null && dim.lowest_score !== null && dim.lowest_score > dim.highest_score) {
      errors.push({
        field: 'score_range',
        message: `${dim.name} 的最低分不能大于最高分`,
        dimension: dim.name
      })
    }
  }

  const categories = dimensions
    .map(dim => dim.dimension_category?.trim())
    .filter(cat => cat && cat.length > 0)
  const uniqueCategories = new Set(categories)
  if (uniqueCategories.size < categories.length) {
    errors.push({
      field: 'category',
      message: '评分维度类别不能重复',
      dimension: null
    })
  }

  return errors
}

export function addDimension(dimensions) {
  const newDimension = {
    name: '',
    full_score: 10,
    highest_score: null,
    lowest_score: null,
    evaluation_content: ''
  }
  dimensions.push(newDimension)
  return dimensions
}

export function removeDimension(dimensions, index) {
  if (dimensions.length <= 1) {
    return { success: false, message: '至少保留一个维度', dimensions }
  }
  dimensions.splice(index, 1)
  return { success: true, message: '删除成功', dimensions }
}

export function calculateTotalFullScore(dimensions) {
  return dimensions.reduce((sum, dim) => sum + (dim.full_score || 0), 0)
}