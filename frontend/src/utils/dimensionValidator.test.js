import { describe, it, expect } from 'vitest'
import {
  validateDimensions,
  addDimension,
  removeDimension,
  calculateTotalFullScore
} from './dimensionValidator'

describe('评分维度管理模块 - 单元测试', () => {
  const validDimensions = [
    { name: '工作反馈深度', full_score: 14, highest_score: null, lowest_score: null, evaluation_content: '问题发现+分析+解决方案' },
    { name: '进度节点明确', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '项目是否有明确进度/节点' }
  ]

  describe('validateDimensions', () => {
    it('应该验证所有字段都有效的情况', () => {
      const errors = validateDimensions(validDimensions)
      expect(errors).toEqual([])
    })

    it('应该检测空维度名称', () => {
      const dimensions = [
        { name: '', full_score: 14, highest_score: null, lowest_score: null, evaluation_content: '' },
        { name: '进度节点明确', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '' }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors).toContainEqual(expect.objectContaining({ field: 'name', message: expect.stringContaining('维度名称') }))
    })

    it('应该检测未填写的维度名称', () => {
      const dimensions = [
        { name: '工作反馈深度', full_score: 14 },
        { name: null, full_score: 13 }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors).toContainEqual(expect.objectContaining({ field: 'name' }))
    })

    it('应该检测满分小于等于0的情况', () => {
      const dimensions = [
        { name: '工作反馈深度', full_score: 0, highest_score: null, lowest_score: null },
        { name: '进度节点明确', full_score: -5, highest_score: null, lowest_score: null }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors.filter(e => e.field === 'full_score').length).toBe(2)
    })

    it('应该检测满分未设置的情况', () => {
      const dimensions = [
        { name: '工作反馈深度', full_score: undefined },
        { name: '进度节点明确', full_score: null }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors.filter(e => e.field === 'full_score').length).toBe(2)
    })

    it('应该检测最高分超过满分的情况', () => {
      const dimensions = [
        { name: '工作反馈深度', full_score: 10, highest_score: 15, lowest_score: null }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors).toContainEqual(expect.objectContaining({ field: 'highest_score', message: expect.stringContaining('最高分') }))
    })

    it('应该检测最低分超过满分的情况', () => {
      const dimensions = [
        { name: '工作反馈深度', full_score: 10, highest_score: null, lowest_score: 15 }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors).toContainEqual(expect.objectContaining({ field: 'lowest_score', message: expect.stringContaining('最低分') }))
    })

    it('应该检测最低分大于最高分的情况', () => {
      const dimensions = [
        { name: '工作反馈深度', full_score: 20, highest_score: 10, lowest_score: 15 }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors).toContainEqual(expect.objectContaining({ field: 'score_range', message: expect.stringContaining('最低分不能大于最高分') }))
    })

    it('应该检测重复的维度类别', () => {
      const dimensions = [
        { name: '维度1', full_score: 10, dimension_category: '类别A' },
        { name: '维度2', full_score: 10, dimension_category: '类别A' }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors).toContainEqual(expect.objectContaining({ field: 'category', message: expect.stringContaining('不能重复') }))
    })

    it('空的维度类别不应该触发重复检测', () => {
      const dimensions = [
        { name: '维度1', full_score: 10, dimension_category: '' },
        { name: '维度2', full_score: 10, dimension_category: '' }
      ]
      const errors = validateDimensions(dimensions)
      const categoryErrors = errors.filter(e => e.field === 'category')
      expect(categoryErrors).toEqual([])
    })

    it('应该允许最高分和最低分都为空', () => {
      const dimensions = [
        { name: '工作反馈深度', full_score: 14, highest_score: null, lowest_score: null }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors).toEqual([])
    })

    it('应该允许只有最高分或只有最低分', () => {
      const dimensions1 = [{ name: '工作反馈深度', full_score: 14, highest_score: 14, lowest_score: null }]
      const dimensions2 = [{ name: '工作反馈深度', full_score: 14, highest_score: null, lowest_score: 0 }]
      
      const errors1 = validateDimensions(dimensions1)
      const errors2 = validateDimensions(dimensions2)
      
      expect(errors1).toEqual([])
      expect(errors2).toEqual([])
    })

    it('应该允许最高分离散等于满分', () => {
      const dimensions = [
        { name: '工作反馈深度', full_score: 14, highest_score: 14, lowest_score: 0 }
      ]
      const errors = validateDimensions(dimensions)
      expect(errors).toEqual([])
    })
  })

  describe('addDimension', () => {
    it('应该添加一个新的维度', () => {
      const dimensions = [{ name: '工作反馈深度', full_score: 14 }]
      const result = addDimension([...dimensions])
      
      expect(result.length).toBe(2)
      expect(result[1]).toEqual({
        name: '',
        full_score: 10,
        highest_score: null,
        lowest_score: null,
        evaluation_content: ''
      })
    })

    it('应该保持原数组不变', () => {
      const original = [{ name: '工作反馈深度', full_score: 14 }]
      const originalLength = original.length
      
      addDimension(original)
      
      expect(original.length).toBe(originalLength + 1)
    })

    it('应该添加多个维度', () => {
      const dimensions = [{ name: '维度1', full_score: 10 }]
      const result1 = addDimension([...dimensions])
      const result2 = addDimension([...result1])
      
      expect(result1.length).toBe(2)
      expect(result2.length).toBe(3)
    })
  })

  describe('removeDimension', () => {
    it('应该删除指定索引的维度', () => {
      const dimensions = [
        { name: '维度1', full_score: 10 },
        { name: '维度2', full_score: 20 },
        { name: '维度3', full_score: 30 }
      ]
      
      const result = removeDimension(dimensions, 1)
      
      expect(result.success).toBe(true)
      expect(result.dimensions.length).toBe(2)
      expect(result.dimensions[0].name).toBe('维度1')
      expect(result.dimensions[1].name).toBe('维度3')
    })

    it('应该拒绝删除最后一个维度', () => {
      const dimensions = [{ name: '唯一维度', full_score: 10 }]
      
      const result = removeDimension(dimensions, 0)
      
      expect(result.success).toBe(false)
      expect(result.message).toBe('至少保留一个维度')
      expect(result.dimensions.length).toBe(1)
    })

    it('应该处理边界索引', () => {
      const dimensions = [
        { name: '维度1', full_score: 10 },
        { name: '维度2', full_score: 20 }
      ]
      
      const result1 = removeDimension(dimensions, 0)
      expect(result1.success).toBe(true)
      expect(result1.dimensions.length).toBe(1)
      
      const result2 = removeDimension(result1.dimensions, 0)
      expect(result2.success).toBe(false)
    })

    it('应该正确处理删除后的数组', () => {
      const dimensions = [
        { name: 'A', full_score: 10 },
        { name: 'B', full_score: 20 },
        { name: 'C', full_score: 30 },
        { name: 'D', full_score: 40 }
      ]
      
      const result = removeDimension(dimensions, 2)
      
      expect(result.dimensions).toEqual([
        { name: 'A', full_score: 10 },
        { name: 'B', full_score: 20 },
        { name: 'D', full_score: 40 }
      ])
    })
  })

  describe('calculateTotalFullScore', () => {
    it('应该计算所有维度的满分总和', () => {
      const dimensions = [
        { name: '维度1', full_score: 10 },
        { name: '维度2', full_score: 20 },
        { name: '维度3', full_score: 30 }
      ]
      
      const total = calculateTotalFullScore(dimensions)
      
      expect(total).toBe(60)
    })

    it('应该处理空数组', () => {
      const total = calculateTotalFullScore([])
      expect(total).toBe(0)
    })

    it('应该处理未设置满分的维度', () => {
      const dimensions = [
        { name: '维度1', full_score: 10 },
        { name: '维度2', full_score: null },
        { name: '维度3', full_score: undefined },
        { name: '维度4', full_score: 30 }
      ]
      
      const total = calculateTotalFullScore(dimensions)
      
      expect(total).toBe(40)
    })

    it('应该处理单个维度', () => {
      const dimensions = [{ name: '唯一维度', full_score: 100 }]
      
      const total = calculateTotalFullScore(dimensions)
      
      expect(total).toBe(100)
    })

    it('应该处理大型维度数组', () => {
      const dimensions = Array.from({ length: 100 }, (_, i) => ({
        name: `维度${i + 1}`,
        full_score: i + 1
      }))
      
      const total = calculateTotalFullScore(dimensions)
      
      expect(total).toBe(5050)
    })
  })
})