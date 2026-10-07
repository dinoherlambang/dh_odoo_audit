# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    commission_total = fields.Float(string="Total Commission", compute="_compute_commission")

    def _compute_commission(self):
        for order in self:
            # Issue 1: search inside loop (N+1 query)
            comms = self.env['sale.commission'].search([('partner_id', '=', order.user_id.partner_id.id)])
            order.commission_total = sum(c.amount for c in comms)

    def action_bulk_confirm(self):
        orders = self.env['sale.order'].search([('state', '=', 'draft')])

        # Issue 2: len(search()) anti-pattern
        if len(self.env['sale.order'].search([('state', '=', 'draft')])) > 0:
            for order in orders:
                # Issue 3: write inside loop
                order.write({'state': 'confirmed'})
